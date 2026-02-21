from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Annotated

from models.user import User
from api.dependencies import get_current_active_user
from schemas.file import FileUploadResponse, FileDownloadResponse, FileMetadata
from utils.storage import storage
from utils.logger import logger
from config import settings
from datetime import datetime

router = APIRouter()


def validate_file_size(file: UploadFile) -> None:
    """Validate file size is within limits"""
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
    
    # Read file to check size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB"
        )


def validate_file_type(filename: str) -> None:
    """Validate file type is allowed"""
    allowed_types = settings.ALLOWED_FILE_TYPES.split(',')
    file_extension = filename.split('.')[-1].lower() if '.' in filename else ''
    
    if file_extension not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{file_extension}' not allowed. Allowed types: {', '.join(allowed_types)}"
        )


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: Annotated[UploadFile, File(description="File to upload")],
    prefix: str = "uploads",
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a file to storage.
    
    - **file**: File to upload (PDF, DOCX, TXT, PPTX)
    - **prefix**: Optional prefix for file organization
    
    Returns file metadata including unique ID and checksum.
    """
    # Validate file
    validate_file_type(file.filename)
    validate_file_size(file)
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Upload to storage
        file_key, file_id, checksum = storage.upload_file(
            file_data=file_content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            prefix=prefix,
            metadata={
                'uploaded-by': str(current_user.id),
                'user-email': current_user.email
            }
        )
        
        logger.info(
            f"File uploaded by user {current_user.email}: "
            f"{file.filename} -> {file_key}"
        )
        
        return FileUploadResponse(
            file_id=file_id,
            file_key=file_key,
            file_name=file.filename,
            file_size=len(file_content),
            checksum=checksum,
            upload_date=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/download/{file_key:path}", response_model=FileDownloadResponse)
async def get_download_url(
    file_key: str,
    expiration: int = 3600,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get pre-signed download URL for a file.
    
    - **file_key**: S3 key of the file
    - **expiration**: URL expiration time in seconds (default: 3600 = 1 hour)
    
    Returns pre-signed URL valid for specified duration.
    """
    try:
        # Check if file exists
        if not storage.file_exists(file_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Generate pre-signed URL
        download_url = storage.generate_presigned_url(file_key, expiration)
        
        # Extract filename from key
        filename = file_key.split('/')[-1]
        
        logger.info(
            f"Generated download URL for {file_key} "
            f"(user: {current_user.email}, expires: {expiration}s)"
        )
        
        return FileDownloadResponse(
            download_url=download_url,
            expires_in=expiration,
            file_name=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate download URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.delete("/{file_key:path}")
async def delete_file(
    file_key: str,
    permanent: bool = False,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a file from storage.
    
    - **file_key**: S3 key of the file
    - **permanent**: If True, permanently delete; if False, soft delete (default)
    
    Soft delete retains file for 30 days with deletion marker.
    """
    try:
        # Check if file exists
        if not storage.file_exists(file_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Delete file
        storage.delete_file(file_key, soft_delete=not permanent)
        
        delete_type = "permanently" if permanent else "soft"
        logger.info(
            f"File {delete_type} deleted: {file_key} "
            f"(user: {current_user.email})"
        )
        
        return {
            "message": f"File {delete_type} deleted successfully",
            "file_key": file_key
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.post("/version/{file_key:path}", response_model=dict)
async def create_file_version(
    file_key: str,
    file: Annotated[UploadFile, File(description="New version of file")],
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new version of an existing file.
    
    - **file_key**: S3 key of the original file
    - **file**: New version file content
    
    Returns new version key.
    """
    try:
        # Check if original file exists
        if not storage.file_exists(file_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original file not found"
            )
        
        # Read new file content
        file_content = await file.read()
        
        # Create version
        version_key = storage.create_version(file_key, file_content)
        
        logger.info(
            f"Created file version: {version_key} of {file_key} "
            f"(user: {current_user.email})"
        )
        
        return {
            "message": "File version created successfully",
            "original_key": file_key,
            "version_key": version_key,
            "version_timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create file version: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create file version: {str(e)}"
        )


@router.get("/exists/{file_key:path}")
async def check_file_exists(
    file_key: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Check if a file exists in storage.
    
    - **file_key**: S3 key of the file
    
    Returns existence status.
    """
    exists = storage.file_exists(file_key)
    
    return {
        "file_key": file_key,
        "exists": exists
    }
