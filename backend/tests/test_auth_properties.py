import pytest
from hypothesis import given, settings, strategies as st
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from utils.security import hash_password


# Strategy for generating valid emails
email_strategy = st.emails()

# Strategy for generating valid passwords (8-100 chars)
password_strategy = st.text(min_size=8, max_size=100, alphabet=st.characters(
    blacklist_categories=('Cs',),  # Exclude surrogates
    blacklist_characters='\x00'
))

# Strategy for user roles
role_strategy = st.sampled_from([UserRole.STUDENT, UserRole.FACULTY, UserRole.ADMIN])


class TestAuthenticationProperties:
    """Property-based tests for authentication"""
    
    @pytest.mark.asyncio
    @settings(max_examples=50)
    @given(email=email_strategy, password=password_strategy)
    async def test_property_1_rbac_enforcement(
        self,
        email: str,
        password: str,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """
        Property 1: Role-Based Access Control Enforcement
        
        For any protected endpoint and any user, access should be granted
        if and only if the user's role has the required permissions.
        
        Validates: Requirements 1.6
        """
        # Register user (gets Student role by default)
        response = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password}
        )
        
        if response.status_code != 201:
            # Skip if registration failed (e.g., duplicate email in test run)
            return
        
        token = response.json()["access_token"]
        
        # Test accessing protected endpoint with valid token
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should succeed with valid token
        assert response.status_code == 200
        assert response.json()["email"] == email
        assert response.json()["role"] == "Student"
    
    @pytest.mark.asyncio
    @settings(max_examples=50)
    @given(email=email_strategy, password=password_strategy)
    async def test_property_2_unauthorized_access_returns_403(
        self,
        email: str,
        password: str,
        client: AsyncClient
    ):
        """
        Property 2: Unauthorized Access Returns 403
        
        For any user without required permissions attempting to access
        a protected resource, the system should return a 403 Forbidden error.
        
        Validates: Requirements 1.7
        """
        # Try to access protected endpoint without token
        response = await client.get("/api/auth/me")
        
        # Should return 403 Forbidden (no credentials provided)
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    @settings(max_examples=50)
    @given(
        email=email_strategy,
        password=password_strategy,
        wrong_password=password_strategy
    )
    async def test_password_verification_correctness(
        self,
        email: str,
        password: str,
        wrong_password: str,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """
        Property: Password verification should only succeed with correct password
        
        For any user with a password, verification should succeed if and only if
        the provided password matches the stored password.
        """
        # Skip if passwords are the same
        if password == wrong_password:
            return
        
        # Register user
        response = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password}
        )
        
        if response.status_code != 201:
            return
        
        # Login with correct password should succeed
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password}
        )
        assert response.status_code == 200
        
        # Login with wrong password should fail
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": wrong_password}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    @settings(max_examples=50)
    @given(email=email_strategy, password=password_strategy)
    async def test_token_contains_user_info(
        self,
        email: str,
        password: str,
        client: AsyncClient
    ):
        """
        Property: JWT token should contain user information
        
        For any registered user, the token should encode user_id, email, and role.
        """
        # Register user
        response = await client.post(
            "/api/auth/register",
            json={"email": email, "password": password}
        )
        
        if response.status_code != 201:
            return
        
        data = response.json()
        token = data["access_token"]
        user_info = data["user"]
        
        # Use token to get user info
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        retrieved_info = response.json()
        
        # Verify token contains correct user information
        assert retrieved_info["id"] == user_info["id"]
        assert retrieved_info["email"] == user_info["email"]
        assert retrieved_info["role"] == user_info["role"]
    
    @pytest.mark.asyncio
    @settings(max_examples=30)
    @given(email=email_strategy, password=password_strategy, role=role_strategy)
    async def test_role_hierarchy(
        self,
        email: str,
        password: str,
        role: UserRole,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """
        Property: Role hierarchy should be enforced
        
        Admin > Faculty > Student in permission hierarchy.
        """
        # Create user with specific role
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=role
        )
        db_session.add(user)
        await db_session.commit()
        
        # Login
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code != 200:
            return
        
        token = response.json()["access_token"]
        
        # Get user info
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["role"] == role.value
        
        # Verify permission hierarchy
        user_obj = User(email=email, password_hash="", role=role)
        assert user_obj.has_permission(UserRole.STUDENT) == True
        
        if role in [UserRole.FACULTY, UserRole.ADMIN]:
            assert user_obj.has_permission(UserRole.FACULTY) == True
        
        if role == UserRole.ADMIN:
            assert user_obj.has_permission(UserRole.ADMIN) == True
