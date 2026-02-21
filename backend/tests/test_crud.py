import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserRole
from utils.security import hash_password


class TestCRUDOperations:
    """Unit tests for CRUD API endpoints"""
    
    @pytest.fixture
    async def faculty_token(self, client: AsyncClient, db_session: AsyncSession):
        """Create faculty user and return auth token"""
        user = User(
            email="faculty@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        response = await client.post(
            "/api/auth/login",
            json={"email": "faculty@example.com", "password": "password123"}
        )
        return response.json()["access_token"]
    
    @pytest.mark.asyncio
    async def test_create_subject(self, client: AsyncClient, faculty_token: str):
        """Test creating a subject"""
        response = await client.post(
            "/api/subjects",
            json={
                "name": "Data Structures",
                "code": "CS201",
                "description": "Introduction to data structures"
            },
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Data Structures"
        assert data["code"] == "CS201"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_list_subjects(self, client: AsyncClient, faculty_token: str):
        """Test listing subjects"""
        # Create a subject first
        await client.post(
            "/api/subjects",
            json={"name": "Algorithms", "code": "CS202"},
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        # List subjects
        response = await client.get(
            "/api/subjects",
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    @pytest.mark.asyncio
    async def test_get_subject(self, client: AsyncClient, faculty_token: str):
        """Test getting a specific subject"""
        # Create subject
        create_response = await client.post(
            "/api/subjects",
            json={"name": "Operating Systems", "code": "CS301"},
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        subject_id = create_response.json()["id"]
        
        # Get subject
        response = await client.get(
            f"/api/subjects/{subject_id}",
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == subject_id
        assert data["name"] == "Operating Systems"
    
    @pytest.mark.asyncio
    async def test_update_subject(self, client: AsyncClient, faculty_token: str):
        """Test updating a subject"""
        # Create subject
        create_response = await client.post(
            "/api/subjects",
            json={"name": "Networks", "code": "CS401"},
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        subject_id = create_response.json()["id"]
        
        # Update subject
        response = await client.put(
            f"/api/subjects/{subject_id}",
            json={"name": "Computer Networks"},
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Computer Networks"
        assert data["code"] == "CS401"  # Unchanged
    
    @pytest.mark.asyncio
    async def test_delete_subject(self, client: AsyncClient, faculty_token: str):
        """Test deleting a subject"""
        # Create subject
        create_response = await client.post(
            "/api/subjects",
            json={"name": "Database Systems", "code": "CS501"},
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        subject_id = create_response.json()["id"]
        
        # Delete subject
        response = await client.delete(
            f"/api/subjects/{subject_id}",
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        
        assert response.status_code == 204
        
        # Verify deletion
        get_response = await client.get(
            f"/api/subjects/{subject_id}",
            headers={"Authorization": f"Bearer {faculty_token}"}
        )
        assert get_response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_create_subject_requires_faculty(self, client: AsyncClient):
        """Test that creating subject requires faculty role"""
        # Register as student
        response = await client.post(
            "/api/auth/register",
            json={"email": "student@example.com", "password": "password123"}
        )
        student_token = response.json()["access_token"]
        
        # Try to create subject as student
        response = await client.post(
            "/api/subjects",
            json={"name": "Test Subject", "code": "TEST"},
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 403  # Forbidden
