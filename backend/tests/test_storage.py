import pytest
from io import BytesIO
from utils.storage import S3Storage


class TestFileStorage:
    """Unit tests for file storage operations"""
    
    @pytest.fixture
    def storage(self):
        """Create storage instance for testing"""
        return S3Storage()
    
    @pytest.fixture
    def sample_file_data(self):
        """Sample file data for testing"""
        return b"This is test file content for AURORA Assess"
    
    def test_generate_unique_id(self, storage: S3Storage):
        """Test unique ID generation"""
        id1 = storage.generate_unique_id()
        id2 = storage.generate_unique_id()
        
        assert id1 != id2
        assert len(id1) == 36  # UUID format
        assert len(id2) == 36
    
    def test_calculate_checksum(self, storage: S3Storage, sample_file_data: bytes):
        """Test checksum calculation"""
        checksum1 = storage.calculate_checksum(sample_file_data)
        checksum2 = storage.calculate_checksum(sample_file_data)
        
        # Same data should produce same checksum
        assert checksum1 == checksum2
        assert len(checksum1) == 32  # MD5 hex length
    
    def test_upload_and_download_file(self, storage: S3Storage, sample_file_data: bytes):
        """Test file upload and download round-trip"""
        file_name = "test_file.txt"
        
        # Upload file
        file_id, checksum, file_size = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name,
            content_type="text/plain"
        )
        
        assert file_id is not None
        assert checksum is not None
        assert file_size == len(sample_file_data)
        
        # Download file
        downloaded_data = storage.download_file(file_id, file_name)
        
        # Verify content matches
        assert downloaded_data == sample_file_data
    
    def test_upload_file_with_metadata(self, storage: S3Storage, sample_file_data: bytes):
        """Test file upload with custom metadata"""
        file_name = "test_with_metadata.txt"
        metadata = {
            "user-id": "test-user-123",
            "subject": "Mathematics"
        }
        
        file_id, checksum, file_size = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name,
            metadata=metadata
        )
        
        assert file_id is not None
        assert checksum is not None
    
    def test_download_nonexistent_file(self, storage: S3Storage):
        """Test downloading non-existent file raises exception"""
        with pytest.raises(Exception, match="File not found"):
            storage.download_file("nonexistent-id", "nonexistent.txt")
    
    def test_generate_presigned_url(self, storage: S3Storage, sample_file_data: bytes):
        """Test pre-signed URL generation"""
        file_name = "test_presigned.txt"
        
        # Upload file first
        file_id, _, _ = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name
        )
        
        # Generate pre-signed URL
        url = storage.generate_presigned_url(file_id, file_name, expiration=3600)
        
        assert url is not None
        assert "http" in url
        assert file_id in url or file_name in url
    
    def test_soft_delete_file(self, storage: S3Storage, sample_file_data: bytes):
        """Test soft deletion of file"""
        file_name = "test_soft_delete.txt"
        
        # Upload file
        file_id, _, _ = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name
        )
        
        # Soft delete
        result = storage.delete_file(file_id, file_name, soft_delete=True)
        assert result is True
        
        # File should still be downloadable after soft delete
        downloaded_data = storage.download_file(file_id, file_name)
        assert downloaded_data == sample_file_data
    
    def test_permanent_delete_file(self, storage: S3Storage, sample_file_data: bytes):
        """Test permanent deletion of file"""
        file_name = "test_permanent_delete.txt"
        
        # Upload file
        file_id, _, _ = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name
        )
        
        # Permanent delete
        result = storage.delete_file(file_id, file_name, soft_delete=False)
        assert result is True
        
        # File should not be downloadable after permanent delete
        with pytest.raises(Exception, match="File not found"):
            storage.download_file(file_id, file_name)
    
    def test_verify_file_integrity_success(self, storage: S3Storage, sample_file_data: bytes):
        """Test file integrity verification with correct checksum"""
        file_name = "test_integrity.txt"
        
        # Upload file
        file_id, checksum, _ = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name
        )
        
        # Verify integrity
        is_valid = storage.verify_file_integrity(file_id, file_name, checksum)
        assert is_valid is True
    
    def test_verify_file_integrity_failure(self, storage: S3Storage, sample_file_data: bytes):
        """Test file integrity verification with incorrect checksum"""
        file_name = "test_integrity_fail.txt"
        
        # Upload file
        file_id, _, _ = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name
        )
        
        # Verify with wrong checksum
        wrong_checksum = "0" * 32
        is_valid = storage.verify_file_integrity(file_id, file_name, wrong_checksum)
        assert is_valid is False
    
    def test_create_file_version(self, storage: S3Storage, sample_file_data: bytes):
        """Test creating a new version of a file"""
        file_name = "test_versioning.txt"
        
        # Upload original file
        file_id, original_checksum, _ = storage.upload_file(
            file_data=sample_file_data,
            file_name=file_name
        )
        
        # Create new version with different content
        new_data = b"This is the updated version of the file"
        version_id, new_checksum = storage.create_file_version(
            file_id=file_id,
            old_file_name=file_name,
            new_file_data=new_data,
            new_file_name=file_name
        )
        
        assert version_id is not None
        assert new_checksum != original_checksum
    
    def test_checksum_consistency(self, storage: S3Storage):
        """Test that same content always produces same checksum"""
        data1 = b"Consistent content"
        data2 = b"Consistent content"
        data3 = b"Different content"
        
        checksum1 = storage.calculate_checksum(data1)
        checksum2 = storage.calculate_checksum(data2)
        checksum3 = storage.calculate_checksum(data3)
        
        assert checksum1 == checksum2
        assert checksum1 != checksum3
