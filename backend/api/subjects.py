from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from database import get_db
from models.user import User
from models.academic import Subject
from schemas.academic import SubjectCreate, SubjectResponse, SubjectUpdate
from api.dependencies import get_current_active_user, require_faculty
from utils.logger import logger

router = APIRouter()


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_data: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Create a new subject (Faculty/Admin only).
    
    - **name**: Subject name
    - **code**: Unique subject code
    - **description**: Optional description
    """
    # Check if code already exists
    result = await db.execute(select(Subject).where(Subject.code == subject_data.code))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject with code '{subject_data.code}' already exists"
        )
    
    # Create subject
    subject = Subject(**subject_data.model_dump())
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    
    logger.info(f"Subject created: {subject.code} by user {current_user.email}")
    
    return SubjectResponse.model_validate(subject)


@router.get("", response_model=List[SubjectResponse])
async def list_subjects(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all subjects.
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    result = await db.execute(
        select(Subject).offset(skip).limit(limit)
    )
    subjects = result.scalars().all()
    
    return [SubjectResponse.model_validate(s) for s in subjects]


@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific subject by ID."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    return SubjectResponse.model_validate(subject)


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: UUID,
    subject_data: SubjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Update a subject (Faculty/Admin only)."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    # Update fields
    update_data = subject_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subject, field, value)
    
    await db.commit()
    await db.refresh(subject)
    
    logger.info(f"Subject updated: {subject.code} by user {current_user.email}")
    
    return SubjectResponse.model_validate(subject)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Delete a subject (Faculty/Admin only)."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
    
    await db.delete(subject)
    await db.commit()
    
    logger.info(f"Subject deleted: {subject.code} by user {current_user.email}")
    
    return None
