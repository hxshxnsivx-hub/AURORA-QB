import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

from models.user import User, UserRole
from utils.security import hash_password
from utils.storage import storage


class TestFileOperations:
    """Unit tests for file storage operations"""
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful file upload"""
        # Create and login user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "password123"}
        )
        token = login_response.json()["access_token"]
        
        # Upload file
        file_content = b"Test file content for upload"
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
        
        response = await client.post(
            "/api/files/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert "file_key" in data
        assert "checksum" in data
        assert data["file_name"] == "test.txt"
        assert data["file_size"] == len(file_content)
    
    @pytest.mark.asyncio
    async def test_upload_file_invalid_type(self, client: AsyncClient, db_session: AsyncSession):
        """Test upload with invalid file type"""
        # Create and login user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "password123"}
        )
        token = login_response.json()["access_token"]
        
        # Try to upload invalid file type
        file_content = b"Invalid file"
        files = {"file": ("test.exe", BytesIO(file_content), "application/x-msdownload")}
        
        response = await client.post(
            "/api/files/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_upload_file_no_auth(self, client: AsyncClient):
        """Test upload without authentication fails"""
        file_content = b"Test file"
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
        
        response = await client.post("/api/files/upload", files=files)
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_get_download_url(self, client: AsyncClient, db_session: AsyncSession):
        """Test generating download URL"""
        # Create and login user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "password123"}
        )
        token = login_response.json()["access_token"]
        
        # Upload file first
        file_content = b"Test file for download"
        files = {"file": ("download_test.txt", BytesIO(file_content), "text/plain")}
        
        upload_response = await client.post(
            "/api/files/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"}
        )
        file_key = upload_response.json()["file_key"]
        
        # Get download URL
        response = await client.get(
            f"/api/files/download/{file_key}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert data["expires_in"] == 3600
        assert "download_test.txt" in data["file_name"]
    
    @pytest.mark.asyncio
    async def test_get_download_url_nonexistent(self, client: AsyncClient, db_session: AsyncSession):
        """Test download URL for non-existent file"""
        # Create and login user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "password123"}
        )
        token = login_response.json()["access_token"]
        
        # Try to get URL for non-existent file
        response = await client.get(
            "/api/files/download/nonexistent/file.txt",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_file_soft(self, client: AsyncClient, db_session: AsyncSession):
        """Test soft delete of file"""
        # Create and login user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "password123"}
        )
        token = login_response.json()["access_token"]
        
        # Upload file
        file_content = b"File to delete"
        files = {"file": ("delete_test.txt", BytesIO(file_content), "text/plain")}
        
        upload_response = await client.post(
            "/api/files/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"}
        )
        file_key = upload_response.json()["file_key"]
        
        # Soft delete file
        response = await client.delete(
            f"/api/files/{file_key}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert "soft" in response.json()["message"].lower()
    
    @pytest.mark.asyncio
    async def test_check_file_exists(self, client: AsyncClient, db_session: AsyncSession):
        """Test checking file existence"""
        # Create and login user
        user = User(
            email="testuser@example.com",
            password_hash=hash_password("password123"),
            role=UserRole.FACULTY
        )
        db_session.add(user)
        await db_session.commit()
        
        login_response = await client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "password123"}
        )
        token = login_response.json()["access_token"]
        
        # Upload file
        file_content = b"Existence test"
        files = {"file": ("exists_test.txt", BytesIO(file_content), "text/plain")}
        
        upload_response = await client.post(
            "/api/files/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"}
        )
        file_key = upload_response.json()["file_key"]
        
        # Check existence
        response = await client.get(
            f"/api/files/exists/{file_key}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["exists"] == True
        
        # Check non-existent file
        response = await client.get(
            "/api/files/exists/nonexistent/file.txt",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["exists"] == False
