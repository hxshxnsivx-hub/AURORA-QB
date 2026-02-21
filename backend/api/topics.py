from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from database import get_db
from models.user import User
from models.academic import Topic
from schemas.academic import TopicCreate, TopicResponse, TopicUpdate
from api.dependencies import get_current_active_user, require_faculty

router = APIRouter()


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    topic_data: TopicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Create a new topic (Faculty/Admin only)."""
    topic = Topic(**topic_data.model_dump())
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return TopicResponse.model_validate(topic)


@router.get("", response_model=List[TopicResponse])
async def list_topics(
    unit_id: UUID = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List topics, optionally filtered by unit."""
    query = select(Topic)
    if unit_id:
        query = query.where(Topic.unit_id == unit_id)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    topics = result.scalars().all()
    return [TopicResponse.model_validate(t) for t in topics]


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific topic by ID."""
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    
    return TopicResponse.model_validate(topic)


@router.put("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: UUID,
    topic_data: TopicUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Update a topic (Faculty/Admin only)."""
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    
    update_data = topic_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(topic, field, value)
    
    await db.commit()
    await db.refresh(topic)
    return TopicResponse.model_validate(topic)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Delete a topic (Faculty/Admin only)."""
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    
    await db.delete(topic)
    await db.commit()
    return None
