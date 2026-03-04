"""API endpoints for resource management"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID, uuid4

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.resource import Resource, ResourceTopicLink
from schemas.resource import (
    ResourceResponse,
    ResourceUploadResponse,
    ResourceSearchRequest,
    ResourceSearchResponse
)
from utils.storage import upload_file, delete_file
from llm.embeddings import generate_embedding
from utils.logger import logger


router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("/upload", response_model=ResourceUploadResponse)
async def upload_resource(
    file: UploadFile = File(...),
    title: str = None,
    subject_id: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Upload a resource file"""
    
    # Validate file type
    allowed_types = ["pdf", "docx", "pptx", "txt"]
    file_ext = file.filename.split(".")[-1].lower()
    
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(allowed_types)}"
        )
    
    # Upload file to storage
    file_id = str(uuid4())
    file_path = f"resources/{file_id}.{file_ext}"
    
    content = await file.read()
    await upload_file(file_path, content)
    
    # Generate embedding (simplified - would extract text first)
    embedding = await generate_embedding(title or file.filename)
    
    # Create resource record
    resource = Resource(
        title=title or file.filename,
        file_path=file_path,
        resource_type=file_ext,
        embedding=embedding
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    
    logger.info("Resource uploaded", extra={
        "resource_id": str(resource.id),
        "faculty_id": str(current_user.id)
    })
    
    return ResourceUploadResponse(
        id=resource.id,
        title=resource.title,
        file_path=resource.file_path,
        resource_type=resource.resource_type
    )


@router.post("/{resource_id}/link-topic")
async def link_resource_to_topic(
    resource_id: UUID,
    topic_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Link a resource to a topic"""
    
    # Check if resource exists
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # Check if link already exists
    existing = db.query(ResourceTopicLink).filter(
        ResourceTopicLink.resource_id == resource_id,
        ResourceTopicLink.topic_id == topic_id
    ).first()
    
    if existing:
        return {"status": "already_linked"}
    
    # Create link
    link = ResourceTopicLink(
        resource_id=resource_id,
        topic_id=topic_id
    )
    db.add(link)
    db.commit()
    
    return {"status": "linked"}


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """Delete a resource"""
    
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # Delete file from storage
    await delete_file(resource.file_path)
    
    # Delete database record (cascade will handle links)
    db.delete(resource)
    db.commit()
    
    return None


@router.post("/search", response_model=List[ResourceSearchResponse])
async def search_resources(
    request: ResourceSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Semantic search for resources"""
    
    # Generate query embedding
    query_embedding = await generate_embedding(request.query)
    
    # Get resources (simplified - would use pgvector similarity search)
    resources = db.query(Resource).limit(10).all()
    
    # Calculate similarity scores (simplified)
    from llm.embeddings import cosine_similarity
    results = []
    
    for resource in resources:
        if resource.embedding:
            similarity = cosine_similarity(query_embedding, resource.embedding)
            if similarity >= request.min_similarity:
                results.append(ResourceSearchResponse(
                    id=resource.id,
                    title=resource.title,
                    resource_type=resource.resource_type,
                    similarity_score=similarity
                ))
    
    # Sort by similarity
    results.sort(key=lambda x: x.similarity_score, reverse=True)
    
    return results[:request.limit]


@router.get("/", response_model=List[ResourceResponse])
async def list_resources(
    topic_id: UUID = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List resources"""
    
    if topic_id:
        # Get resources for specific topic
        links = db.query(ResourceTopicLink).filter(
            ResourceTopicLink.topic_id == topic_id
        ).all()
        
        resource_ids = [link.resource_id for link in links]
        resources = db.query(Resource).filter(Resource.id.in_(resource_ids)).all()
    else:
        resources = db.query(Resource).all()
    
    return [ResourceResponse.from_orm(r) for r in resources]


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific resource"""
    
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    return ResourceResponse.from_orm(resource)
