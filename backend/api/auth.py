from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from typing import Annotated

from database import get_db
from models.user import User, UserRole
from schemas.auth import UserCreate, UserLogin, UserResponse, Token
from utils.security import hash_password, verify_password, create_access_token
from utils.logger import logger

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    - **email**: Valid email address
    - **password**: Password (minimum 8 characters)
    
    Returns JWT token and user information.
    Default role is Student.
    """
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        logger.warning(f"Registration attempt with existing email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        role=UserRole.STUDENT  # Default role
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Create access token
    access_token = create_access_token(
        data={
            "user_id": str(new_user.id),
            "email": new_user.email,
            "role": new_user.role.value
        }
    )
    
    logger.info(f"New user registered: {new_user.email} (ID: {new_user.id})")
    
    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(new_user)
    )


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.
    
    - **email**: Registered email address
    - **password**: User password
    
    Returns JWT token valid for 24 hours.
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        logger.warning(f"Failed login attempt for email: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value
        }
    )
    
    logger.info(f"User logged in: {user.email} (ID: {user.id})")
    
    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    
    Note: JWT tokens are stateless, so logout is handled client-side
    by removing the token. This endpoint is provided for consistency.
    """
    return {"message": "Successfully logged out"}


from api.dependencies import get_current_active_user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current authenticated user information.
    
    Requires valid JWT token in Authorization header.
    """
    return UserResponse.model_validate(current_user)
