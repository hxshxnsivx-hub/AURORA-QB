import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, BinaryIO, Tuple
from io import BytesIO
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from config import settings
from utils.logger import logger


class S3Storage:
    """S3-compatible storage client for MinIO/AWS S3"""
    
    def __init__(self):
        """Initialize S3 client"""
        self.client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version='s3v4')
        )
        self.bucket_name = settings.S3_BUCKET_NAME
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket '{self.bucket_name}' exists")
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created S3 bucket '{self.bucket_name}'")
            except ClientError as e:
                logger.error(f"Failed to create bucket: {str(e)}")
                raise
    
    def generate_unique_id(self) -> str:
        """
        Generate a unique identifier for file storage.
        
        Returns:
            Unique UUID string
        """
        return str(uuid.uuid4())
    
    def calculate_checksum(self, file_data: bytes) -> str:
        """
        Calculate MD5 checksum of file data.
        
        Args:
            file_data: File content as bytes
            
        Returns:
            MD5 checksum as hex string
        """
        return hashlib.md5(file_data).hexdigest()
    
    def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> Tuple[str, str, int]:
        """
        Upload file to S3 storage.
        
        Args:
            file_data: File content as bytes
            file_name: Original file name
            content_type: MIME type of the file
            metadata: Optional metadata dictionary
            
        Returns:
            Tuple of (file_id, checksum, file_size)
            
        Raises:
            Exception: If upload fails
        """
        file_id = self.generate_unique_id()
        file_size = len(file_data)
        checksum = self.calculate_checksum(file_data)
        
        # Prepare metadata
        file_metadata = {
            'original-filename': file_name,
            'checksum': checksum,
            'upload-timestamp': datetime.utcnow().isoformat()
        }
        if metadata:
            file_metadata.update(metadata)
        
        # Construct S3 key with versioning support
        s3_key = f"files/{file_id}/{file_name}"
        
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_data,
                ContentType=content_type,
                Metadata=file_metadata,
                ContentMD5=hashlib.md5(file_data).digest().hex()
            )
            
            logger.info(
                f"File uploaded successfully",
                extra={
                    "file_id": file_id,
                    "file_name": file_name,
                    "file_size": file_size,
                    "checksum": checksum
                }
            )
            
            return file_id, checksum, file_size
            
        except ClientError as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise Exception(f"File upload failed: {str(e)}")
    
    def download_file(self, file_id: str, file_name: str) -> bytes:
        """
        Download file from S3 storage.
        
        Args:
            file_id: Unique file identifier
            file_name: Original file name
            
        Returns:
            File content as bytes
            
        Raises:
            Exception: If download fails or file not found
        """
        s3_key = f"files/{file_id}/{file_name}"
        
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            file_data = response['Body'].read()
            
            logger.info(
                f"File downloaded successfully",
                extra={"file_id": file_id, "file_name": file_name}
            )
            
            return file_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"File not found: {file_id}/{file_name}")
                raise Exception("File not found")
            else:
                logger.error(f"Failed to download file: {str(e)}")
                raise Exception(f"File download failed: {str(e)}")
    
    def generate_presigned_url(
        self,
        file_id: str,
        file_name: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate pre-signed URL for secure file download.
        
        Args:
            file_id: Unique file identifier
            file_name: Original file name
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Pre-signed URL string
            
        Raises:
            Exception: If URL generation fails
        """
        s3_key = f"files/{file_id}/{file_name}"
        
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            
            logger.info(
                f"Pre-signed URL generated",
                extra={
                    "file_id": file_id,
                    "expiration": expiration
                }
            )
            
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate pre-signed URL: {str(e)}")
            raise Exception(f"URL generation failed: {str(e)}")
    
    def delete_file(self, file_id: str, file_name: str, soft_delete: bool = True) -> bool:
        """
        Delete file from S3 storage.
        
        Args:
            file_id: Unique file identifier
            file_name: Original file name
            soft_delete: If True, mark for deletion; if False, delete immediately
            
        Returns:
            True if successful
            
        Raises:
            Exception: If deletion fails
        """
        s3_key = f"files/{file_id}/{file_name}"
        
        if soft_delete:
            # Add deletion marker metadata
            try:
                # Copy object with deletion metadata
                copy_source = {'Bucket': self.bucket_name, 'Key': s3_key}
                self.client.copy_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    CopySource=copy_source,
                    Metadata={
                        'deleted': 'true',
                        'deletion-timestamp': datetime.utcnow().isoformat()
                    },
                    MetadataDirective='REPLACE'
                )
                
                logger.info(
                    f"File marked for soft deletion",
                    extra={"file_id": file_id, "file_name": file_name}
                )
                
                return True
                
            except ClientError as e:
                logger.error(f"Failed to soft delete file: {str(e)}")
                raise Exception(f"Soft deletion failed: {str(e)}")
        else:
            # Permanent deletion
            try:
                self.client.delete_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
                
                logger.info(
                    f"File permanently deleted",
                    extra={"file_id": file_id, "file_name": file_name}
                )
                
                return True
                
            except ClientError as e:
                logger.error(f"Failed to delete file: {str(e)}")
                raise Exception(f"File deletion failed: {str(e)}")
    
    def verify_file_integrity(
        self,
        file_id: str,
        file_name: str,
        expected_checksum: str
    ) -> bool:
        """
        Verify file integrity by comparing checksums.
        
        Args:
            file_id: Unique file identifier
            file_name: Original file name
            expected_checksum: Expected MD5 checksum
            
        Returns:
            True if checksums match, False otherwise
        """
        try:
            file_data = self.download_file(file_id, file_name)
            actual_checksum = self.calculate_checksum(file_data)
            
            matches = actual_checksum == expected_checksum
            
            if not matches:
                logger.warning(
                    f"File integrity check failed",
                    extra={
                        "file_id": file_id,
                        "expected": expected_checksum,
                        "actual": actual_checksum
                    }
                )
            
            return matches
            
        except Exception as e:
            logger.error(f"Failed to verify file integrity: {str(e)}")
            return False
    
    def create_file_version(
        self,
        file_id: str,
        old_file_name: str,
        new_file_data: bytes,
        new_file_name: str,
        content_type: str = "application/octet-stream"
    ) -> Tuple[str, str]:
        """
        Create a new version of an existing file.
        
        Args:
            file_id: Existing file identifier
            old_file_name: Original file name
            new_file_data: New file content
            new_file_name: New file name
            content_type: MIME type
            
        Returns:
            Tuple of (version_id, checksum)
        """
        version_id = str(uuid.uuid4())
        checksum = self.calculate_checksum(new_file_data)
        
        # Store new version with version ID in path
        s3_key = f"files/{file_id}/versions/{version_id}/{new_file_name}"
        
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=new_file_data,
                ContentType=content_type,
                Metadata={
                    'version-id': version_id,
                    'parent-file-id': file_id,
                    'checksum': checksum,
                    'created-at': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(
                f"File version created",
                extra={
                    "file_id": file_id,
                    "version_id": version_id,
                    "checksum": checksum
                }
            )
            
            return version_id, checksum
            
        except ClientError as e:
            logger.error(f"Failed to create file version: {str(e)}")
            raise Exception(f"Version creation failed: {str(e)}")


# Global storage instance
storage = S3Storage()
