from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from database import get_db
from models.user import User
from models.academic import Unit
from schemas.academic import UnitCreate, UnitResponse, UnitUpdate
from api.dependencies import get_current_active_user, require_faculty

router = APIRouter()


@router.post("", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
async def create_unit(
    unit_data: UnitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Create a new unit (Faculty/Admin only)."""
    unit = Unit(**unit_data.model_dump())
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return UnitResponse.model_validate(unit)


@router.get("", response_model=List[UnitResponse])
async def list_units(
    subject_id: UUID = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List units, optionally filtered by subject."""
    query = select(Unit)
    if subject_id:
        query = query.where(Unit.subject_id == subject_id)
    query = query.offset(skip).limit(limit).order_by(Unit.order)
    
    result = await db.execute(query)
    units = result.scalars().all()
    return [UnitResponse.model_validate(u) for u in units]


@router.get("/{unit_id}", response_model=UnitResponse)
async def get_unit(
    unit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific unit by ID."""
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    
    return UnitResponse.model_validate(unit)


@router.put("/{unit_id}", response_model=UnitResponse)
async def update_unit(
    unit_id: UUID,
    unit_data: UnitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Update a unit (Faculty/Admin only)."""
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    
    update_data = unit_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(unit, field, value)
    
    await db.commit()
    await db.refresh(unit)
    return UnitResponse.model_validate(unit)


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(
    unit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """Delete a unit (Faculty/Admin only)."""
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    
    await db.delete(unit)
    await db.commit()
    return None
