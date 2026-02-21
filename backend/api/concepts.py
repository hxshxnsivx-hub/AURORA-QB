from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from database import get_db
from models.user import User
from models.academic import Concept
from schemas.academic import ConceptCreate, ConceptResponse, ConceptUpdate
from api.dependencies import get_current_active_user, require_faculty

router = APIRouter()


@router.post("", response_model=ConceptResponse, status_code=status.HTTP_201_CREATED)
async def create_concept(
    concept_data: ConceptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Create a new concept (Faculty/Admin only)."""
    concept = Concept(**concept_data.model_dump())
    db.add(concept)
    await db.commit()
    await db.refresh(concept)
    return ConceptResponse.model_validate(concept)


@router.get("", response_model=List[ConceptResponse])
async def list_concepts(
    topic_id: UUID = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List concepts, optionally filtered by topic."""
    query = select(Concept)
    if topic_id:
        query = query.where(Concept.topic_id == topic_id)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    concepts = result.scalars().all()
    return [ConceptResponse.model_validate(c) for c in concepts]


@router.get("/{concept_id}", response_model=ConceptResponse)
async def get_concept(
    concept_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific concept by ID."""
    result = await db.execute(select(Concept).where(Concept.id == concept_id))
    concept = result.scalar_one_or_none()
    
    if not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found")
    
    return ConceptResponse.model_validate(concept)


@router.put("/{concept_id}", response_model=ConceptResponse)
async def update_concept(
    concept_id: UUID,
    concept_data: ConceptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Update a concept (Faculty/Admin only)."""
    result = await db.execute(select(Concept).where(Concept.id == concept_id))
    concept = result.scalar_one_or_none()
    
    if not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found")
    
    update_data = concept_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(concept, field, value)
    
    await db.commit()
    await db.refresh(concept)
    return ConceptResponse.model_validate(concept)


@router.delete("/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_concept(
    concept_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Delete a concept (Faculty/Admin only)."""
    result = await db.execute(select(Concept).where(Concept.id == concept_id))
    concept = result.scalar_one_or_none()
    
    if not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found")
    
    await db.delete(concept)
    await db.commit()
    return None
