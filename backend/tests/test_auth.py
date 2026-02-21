import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User, UserRole
from utils.security import hash_password


class TestAuthentication:
    """Unit tests for authentication endpoints"""
    
    @pytest.mark.asyncio
    async def test_register_new_user(self, client: AsyncClient, db_session: AsyncSession):
        """Test user registration with valid data"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["role"] == "Student"
        
        # Verify user in database
        result = await db_session.execute(
            select(User).where(User.email == "newuser@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.role == UserRole.STUDENT
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, db_session: AsyncSession):
        """Test registration with existing email fails"""
        # Create existing user
        existing_user = User(
            email="existing@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.STUDENT
        )
        db_session.add(existing_user)
        await db_session.commit()
        
        # Try to register with same email
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "existing@example.com",
                "password": "newpassword123"
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email format"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "invalid-email",
                "password": "securepassword123"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with password too short"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "user@example.com",
                "password": "short"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful login with correct credentials"""
        # Create user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("correctpassword"),
            role=UserRole.STUDENT
        )
        db_session.add(user)
        await db_session.commit()
        
        # Login
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "correctpassword"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "testuser@example.com"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, db_session: AsyncSession):
        """Test login fails with incorrect password"""
        # Create user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("correctpassword"),
            role=UserRole.STUDENT
        )
        db_session.add(user)
        await db_session.commit()
        
        # Try login with wrong password
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login fails for non-existent user"""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "somepassword"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting current user info with valid token"""
        # Register user and get token
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "currentuser@example.com",
                "password": "password123"
            }
        )
        token = response.json()["access_token"]
        
        # Get current user info
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "currentuser@example.com"
        assert data["role"] == "Student"
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test getting current user without token fails"""
        response = await client.get("/api/auth/me")
        
        assert response.status_code == 403  # Forbidden (no credentials)
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token fails"""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient):
        """Test logout endpoint"""
        response = await client.post("/api/auth/logout")
        
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()
