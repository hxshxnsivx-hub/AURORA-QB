import pytest
from hypothesis import given, settings, strategies as st
from utils.storage import S3Storage


# Strategy for generating file content
file_content_strategy = st.binary(min_size=1, max_size=10000)

# Strategy for generating file names
file_name_strategy = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='.-_')
).filter(lambda x: len(x) > 0 and not x.startswith('.'))


class TestStorageProperties:
    """Property-based tests for file storage"""
    
    @pytest.fixture
    def storage(self):
        """Create storage instance for testing"""
        return S3Storage()
    
    @pytest.mark.property
    @settings(max_examples=50)
    @given(file_data=file_content_strategy)
    def test_property_6_file_storage_round_trip(
        self,
        file_data: bytes,
        storage: S3Storage
    ):
        """
        Property 6: File Storage Round-Trip
        
        For any uploaded file, storing it in S3 and then retrieving it
        by its unique identifier should return the identical file content
        (verified by checksum).
        
        Validates: Requirements 2.5, 16.6
        """
        file_name = "test_property_6.bin"
        
        # Upload file
        file_id, original_checksum, file_size = storage.upload_file(
            file_data=file_data,
            file_name=file_name
        )
        
        # Verify upload metadata
        assert file_id is not None
        assert original_checksum is not None
        assert file_size == len(file_data)
        
        # Download file
        downloaded_data = storage.download_file(file_id, file_name)
        
        # Verify content matches exactly
        assert downloaded_data == file_data
        
        # Verify checksum matches
        downloaded_checksum = storage.calculate_checksum(downloaded_data)
        assert downloaded_checksum == original_checksum
        
        # Verify integrity check passes
        assert storage.verify_file_integrity(file_id, file_name, original_checksum)
        
        # Cleanup
        storage.delete_file(file_id, file_name, soft_delete=False)
    
    @pytest.mark.property
    @settings(max_examples=50)
    @given(file_data=file_content_strategy)
    def test_property_70_unique_identifier_generation(
        self,
        file_data: bytes,
        storage: S3Storage
    ):
        """
        Property 70: File Upload Unique Identifier
        
        For any uploaded file, a unique identifier should be generated
        and no two files should have the same identifier.
        
        Validates: Requirements 16.2
        """
        file_name = "test_property_70.bin"
        
        # Upload same file twice
        file_id1, checksum1, _ = storage.upload_file(
            file_data=file_data,
            file_name=file_name
        )
        
        file_id2, checksum2, _ = storage.upload_file(
            file_data=file_data,
            file_name=file_name
        )
        
        # File IDs must be different
        assert file_id1 != file_id2
        
        # But checksums should be the same (same content)
        assert checksum1 == checksum2
        
        # Both files should be independently downloadable
        data1 = storage.download_file(file_id1, file_name)
        data2 = storage.download_file(file_id2, file_name)
        
        assert data1 == file_data
        assert data2 == file_data
        
        # Cleanup
        storage.delete_file(file_id1, file_name, soft_delete=False)
        storage.delete_file(file_id2, file_name, soft_delete=False)
    
    @pytest.mark.property
    @settings(max_examples=30)
    @given(file_data=file_content_strategy)
    def test_property_71_presigned_url_generation(
        self,
        file_data: bytes,
        storage: S3Storage
    ):
        """
        Property 71: Pre-Signed URL Generation
        
        For any file access request, a pre-signed URL should be generated
        with expiration time set to 1 hour from generation.
        
        Validates: Requirements 16.3
        """
        file_name = "test_property_71.bin"
        
        # Upload file
        file_id, _, _ = storage.upload_file(
            file_data=file_data,
            file_name=file_name
        )
        
        # Generate pre-signed URL with 1 hour expiration
        url = storage.generate_presigned_url(file_id, file_name, expiration=3600)
        
        # URL should be valid
        assert url is not None
        assert isinstance(url, str)
        assert len(url) > 0
        assert url.startswith('http')
        
        # URL should contain file reference
        assert file_id in url or file_name in url
        
        # Cleanup
        storage.delete_file(file_id, file_name, soft_delete=False)
    
    @pytest.mark.property
    @settings(max_examples=30)
    @given(file_data1=file_content_strategy, file_data2=file_content_strategy)
    def test_checksum_determinism(
        self,
        file_data1: bytes,
        file_data2: bytes,
        storage: S3Storage
    ):
        """
        Property: Checksum calculation is deterministic
        
        For any file content, calculating the checksum multiple times
        should always produce the same result.
        """
        # Calculate checksum multiple times for same data
        checksum1a = storage.calculate_checksum(file_data1)
        checksum1b = storage.calculate_checksum(file_data1)
        
        # Same data should produce same checksum
        assert checksum1a == checksum1b
        
        # Different data should (very likely) produce different checksums
        if file_data1 != file_data2:
            checksum2 = storage.calculate_checksum(file_data2)
            # MD5 collision is extremely unlikely for random data
            assert checksum1a != checksum2
    
    @pytest.mark.property
    @settings(max_examples=30)
    @given(file_data=file_content_strategy)
    def test_soft_delete_preserves_file(
        self,
        file_data: bytes,
        storage: S3Storage
    ):
        """
        Property: Soft deletion preserves file accessibility
        
        For any file that is soft-deleted, the file should still be
        accessible for download (marked for deletion but not removed).
        
        Validates: Requirements 16.5
        """
        file_name = "test_soft_delete_property.bin"
        
        # Upload file
        file_id, checksum, _ = storage.upload_file(
            file_data=file_data,
            file_name=file_name
        )
        
        # Soft delete
        result = storage.delete_file(file_id, file_name, soft_delete=True)
        assert result is True
        
        # File should still be downloadable
        downloaded_data = storage.download_file(file_id, file_name)
        assert downloaded_data == file_data
        
        # Integrity should still be verifiable
        assert storage.verify_file_integrity(file_id, file_name, checksum)
        
        # Cleanup with permanent delete
        storage.delete_file(file_id, file_name, soft_delete=False)
    
    @pytest.mark.property
    @settings(max_examples=30)
    @given(file_data=file_content_strategy)
    def test_permanent_delete_removes_file(
        self,
        file_data: bytes,
        storage: S3Storage
    ):
        """
        Property: Permanent deletion removes file
        
        For any file that is permanently deleted, the file should not
        be accessible for download.
        """
        file_name = "test_permanent_delete_property.bin"
        
        # Upload file
        file_id, _, _ = storage.upload_file(
            file_data=file_data,
            file_name=file_name
        )
        
        # Permanent delete
        result = storage.delete_file(file_id, file_name, soft_delete=False)
        assert result is True
        
        # File should not be downloadable
        with pytest.raises(Exception, match="File not found"):
            storage.download_file(file_id, file_name)
    
    @pytest.mark.property
    @settings(max_examples=30)
    @given(
        original_data=file_content_strategy,
        updated_data=file_content_strategy
    )
    def test_property_72_file_versioning(
        self,
        original_data: bytes,
        updated_data: bytes,
        storage: S3Storage
    ):
        """
        Property 72: File Versioning
        
        For any question bank file update, a new version should be created
        and the previous version should remain accessible.
        
        Validates: Requirements 16.4
        """
        # Skip if data is identical
        if original_data == updated_data:
            return
        
        file_name = "test_property_72.bin"
        
        # Upload original file
        file_id, original_checksum, _ = storage.upload_file(
            file_data=original_data,
            file_name=file_name
        )
        
        # Create new version
        version_id, new_checksum = storage.create_file_version(
            file_id=file_id,
            old_file_name=file_name,
            new_file_data=updated_data,
            new_file_name=file_name
        )
        
        # Version ID should be unique
        assert version_id is not None
        assert version_id != file_id
        
        # Checksums should be different (different content)
        assert new_checksum != original_checksum
        
        # Original file should still be accessible
        original_downloaded = storage.download_file(file_id, file_name)
        assert original_downloaded == original_data
        
        # Cleanup
        storage.delete_file(file_id, file_name, soft_delete=False)
    
    @pytest.mark.property
    @settings(max_examples=30)
    @given(file_data=file_content_strategy)
    def test_integrity_verification_correctness(
        self,
        file_data: bytes,
        storage: S3Storage
    ):
        """
        Property: File integrity verification is correct
        
        For any file, integrity verification should return True if and only if
        the provided checksum matches the actual file checksum.
        """
        file_name = "test_integrity_property.bin"
        
        # Upload file
        file_id, correct_checksum, _ = storage.upload_file(
            file_data=file_data,
            file_name=file_name
        )
        
        # Verification with correct checksum should succeed
        assert storage.verify_file_integrity(file_id, file_name, correct_checksum) is True
        
        # Verification with incorrect checksum should fail
        wrong_checksum = "0" * 32  # Invalid checksum
        assert storage.verify_file_integrity(file_id, file_name, wrong_checksum) is False
        
        # Cleanup
        storage.delete_file(file_id, file_name, soft_delete=False)
