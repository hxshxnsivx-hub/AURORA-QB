import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from utils.security import hash_password


class TestAuthenticationFlow:
    """Integration tests for complete authentication flow"""
    
    @pytest.mark.asyncio
    async def test_complete_registration_and_login_flow(self, client: AsyncClient):
        """Test complete user registration and login flow"""
        # Step 1: Register new user
        register_response = await client.post(
            "/api/auth/register",
            json={
                "email": "integration@example.com",
                "password": "securepass123"
            }
        )
        
        assert register_response.status_code == 201
        register_data = register_response.json()
        assert "access_token" in register_data
        assert register_data["user"]["email"] == "integration@example.com"
        assert register_data["user"]["role"] == "Student"
        
        first_token = register_data["access_token"]
        
        # Step 2: Use token to access protected endpoint
        me_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {first_token}"}
        )
        
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == "integration@example.com"
        
        # Step 3: Logout (client-side, token still valid on server)
        logout_response = await client.post("/api/auth/logout")
        assert logout_response.status_code == 200
        
        # Step 4: Login again with same credentials
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "integration@example.com",
                "password": "securepass123"
            }
        )
        
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        
        # Step 5: Verify new token works
        second_token = login_data["access_token"]
        verify_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {second_token}"}
        )
        
        assert verify_response.status_code == 200


class TestCRUDFlow:
    """Integration tests for complete CRUD operations flow"""
    
    @pytest.fixture
    async def admin_token(self, client: AsyncClient, db_session: AsyncSession):
        """Create admin user and return auth token"""
        user = User(
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN
        )
        db_session.add(user)
        await db_session.commit()
        
        response = await client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "admin123"}
        )
        return response.json()["access_token"]
    
    @pytest.fixture
    async def faculty_token(self, client: AsyncClient, db_session: AsyncSession):
        """Create faculty user and return auth token"""
        user = User(
            email="faculty@example.com",
            password_hash=hash_password("faculty123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        response = await client.post(
            "/api/auth/login",
            json={"email": "faculty@example.com", "password": "faculty123"}
        )
        return response.json()["access_token"]
    
    @pytest.mark.asyncio
    async def test_complete_academic_hierarchy_creation(
        self,
        client: AsyncClient,
        faculty_token: str
    ):
        """Test creating complete academic hierarchy: Subject -> Unit -> Topic -> Concept"""
        headers = {"Authorization": f"Bearer {faculty_token}"}
        
        # Step 1: Create Subject
        subject_response = await client.post(
            "/api/subjects",
            json={
                "name": "Computer Science",
                "code": "CS101",
                "description": "Introduction to Computer Science"
            },
            headers=headers
        )
        
        assert subject_response.status_code == 201
        subject = subject_response.json()
        subject_id = subject["id"]
        
        # Step 2: Create Unit under Subject
        unit_response = await client.post(
            "/api/units",
            json={
                "subject_id": subject_id,
                "name": "Programming Fundamentals",
                "order": 1
            },
            headers=headers
        )
        
        assert unit_response.status_code == 201
        unit = unit_response.json()
        unit_id = unit["id"]
        
        # Step 3: Create Topic under Unit
        topic_response = await client.post(
            "/api/topics",
            json={
                "unit_id": unit_id,
                "name": "Variables and Data Types",
                "description": "Introduction to variables"
            },
            headers=headers
        )
        
        assert topic_response.status_code == 201
        topic = topic_response.json()
        topic_id = topic["id"]
        
        # Step 4: Create Concept under Topic
        concept_response = await client.post(
            "/api/concepts",
            json={
                "topic_id": topic_id,
                "name": "Integer Variables",
                "description": "Whole number variables",
                "importance": 0.8
            },
            headers=headers
        )
        
        assert concept_response.status_code == 201
        concept = concept_response.json()
        
        # Step 5: Verify hierarchy by listing
        units_list = await client.get(
            f"/api/units?subject_id={subject_id}",
            headers=headers
        )
        assert units_list.status_code == 200
        assert len(units_list.json()) == 1
        
        topics_list = await client.get(
            f"/api/topics?unit_id={unit_id}",
            headers=headers
        )
        assert topics_list.status_code == 200
        assert len(topics_list.json()) == 1
        
        concepts_list = await client.get(
            f"/api/concepts?topic_id={topic_id}",
            headers=headers
        )
        assert concepts_list.status_code == 200
        assert len(concepts_list.json()) == 1
    
    @pytest.mark.asyncio
    async def test_user_role_management_flow(
        self,
        client: AsyncClient,
        admin_token: str
    ):
        """Test complete user role management flow"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Step 1: Register a new student
        student_response = await client.post(
            "/api/auth/register",
            json={
                "email": "student@example.com",
                "password": "student123"
            }
        )
        
        assert student_response.status_code == 201
        student_id = student_response.json()["user"]["id"]
        
        # Step 2: Admin lists all users
        users_response = await client.get("/api/users", headers=headers)
        assert users_response.status_code == 200
        users = users_response.json()
        assert len(users) >= 2  # At least admin and student
        
        # Step 3: Admin promotes student to faculty
        promote_response = await client.put(
            f"/api/users/{student_id}/role",
            json={"role": "Faculty"},
            headers=headers
        )
        
        assert promote_response.status_code == 200
        promoted_user = promote_response.json()
        assert promoted_user["role"] == "Faculty"
        
        # Step 4: Verify role change
        user_response = await client.get(
            f"/api/users/{student_id}",
            headers=headers
        )
        
        assert user_response.status_code == 200
        assert user_response.json()["role"] == "Faculty"
    
    @pytest.mark.asyncio
    async def test_unauthorized_access_flow(self, client: AsyncClient):
        """Test that unauthorized access is properly blocked"""
        # Step 1: Try to access protected endpoint without token
        response = await client.get("/api/subjects")
        assert response.status_code == 403
        
        # Step 2: Register as student
        register_response = await client.post(
            "/api/auth/register",
            json={
                "email": "student2@example.com",
                "password": "password123"
            }
        )
        student_token = register_response.json()["access_token"]
        
        # Step 3: Try to create subject as student (requires faculty)
        create_response = await client.post(
            "/api/subjects",
            json={
                "name": "Test Subject",
                "code": "TEST"
            },
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert create_response.status_code == 403
        
        # Step 4: Try to access admin endpoint as student
        users_response = await client.get(
            "/api/users",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert users_response.status_code == 403


class TestFileUploadFlow:
    """Integration tests for file upload and download flow"""
    
    @pytest.fixture
    async def faculty_token(self, client: AsyncClient, db_session: AsyncSession):
        """Create faculty user and return auth token"""
        user = User(
            email="faculty_file@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        response = await client.post(
            "/api/auth/login",
            json={"email": "faculty_file@example.com", "password": "password123"}
        )
        return response.json()["access_token"]
    
    @pytest.mark.asyncio
    async def test_file_storage_integration(self, faculty_token: str):
        """Test file upload, download, and deletion flow"""
        from utils.storage import storage
        
        # Step 1: Upload file
        test_content = b"This is a test file for integration testing"
        file_id, checksum, file_size = storage.upload_file(
            file_data=test_content,
            file_name="test_integration.txt",
            content_type="text/plain",
            metadata={"uploaded_by": "integration_test"}
        )
        
        assert file_id is not None
        assert checksum is not None
        assert file_size == len(test_content)
        
        # Step 2: Download file
        downloaded_content = storage.download_file(file_id, "test_integration.txt")
        assert downloaded_content == test_content
        
        # Step 3: Verify integrity
        is_valid = storage.verify_file_integrity(file_id, "test_integration.txt", checksum)
        assert is_valid is True
        
        # Step 4: Generate pre-signed URL
        url = storage.generate_presigned_url(file_id, "test_integration.txt")
        assert url is not None
        assert "http" in url
        
        # Step 5: Soft delete
        result = storage.delete_file(file_id, "test_integration.txt", soft_delete=True)
        assert result is True
        
        # Step 6: Verify still accessible after soft delete
        still_accessible = storage.download_file(file_id, "test_integration.txt")
        assert still_accessible == test_content
        
        # Step 7: Permanent delete
        result = storage.delete_file(file_id, "test_integration.txt", soft_delete=False)
        assert result is True
        
        # Step 8: Verify not accessible after permanent delete
        with pytest.raises(Exception, match="File not found"):
            storage.download_file(file_id, "test_integration.txt")


class TestEndToEndScenarios:
    """End-to-end integration tests for realistic scenarios"""
    
    @pytest.mark.asyncio
    async def test_new_faculty_onboarding_scenario(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test complete scenario: New faculty creates course structure"""
        # Step 1: Admin creates faculty account
        admin = User(
            email="admin_e2e@example.com",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN
        )
        db_session.add(admin)
        await db_session.commit()
        
        admin_login = await client.post(
            "/api/auth/login",
            json={"email": "admin_e2e@example.com", "password": "admin123"}
        )
        admin_token = admin_login.json()["access_token"]
        
        # Step 2: Register new faculty
        faculty_register = await client.post(
            "/api/auth/register",
            json={
                "email": "newfaculty@example.com",
                "password": "faculty123"
            }
        )
        faculty_id = faculty_register.json()["user"]["id"]
        
        # Step 3: Admin promotes to faculty
        await client.put(
            f"/api/users/{faculty_id}/role",
            json={"role": "Faculty"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Step 4: Faculty logs in
        faculty_login = await client.post(
            "/api/auth/login",
            json={"email": "newfaculty@example.com", "password": "faculty123"}
        )
        faculty_token = faculty_login.json()["access_token"]
        
        # Step 5: Faculty creates subject
        subject_response = await client.post(
            "/api/subjects",
            json={
                "name": "Data Structures",
                "code": "CS201",
                "description": "Advanced data structures"
            },
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        assert subject_response.status_code == 201
        subject_id = subject_response.json()["id"]
        
        # Step 6: Faculty creates multiple units
        for i in range(1, 4):
            unit_response = await client.post(
                "/api/units",
                json={
                    "subject_id": subject_id,
                    "name": f"Unit {i}",
                    "order": i
                },
                headers={"Authorization": f"Bearer {faculty_token}"}
            )
            assert unit_response.status_code == 201
        
        # Step 7: Verify all units created
        units_list = await client.get(
            f"/api/units?subject_id={subject_id}",
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        assert units_list.status_code == 200
        assert len(units_list.json()) == 3
