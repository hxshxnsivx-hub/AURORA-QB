from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated

from database import get_db
from models.user import User, UserRole
from utils.security import decode_access_token, verify_token_expiration
from utils.logger import logger

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("Invalid token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token expiration
    if not verify_token_expiration(payload):
        logger.warning("Expired token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        logger.warning(f"User not found for token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Dependency to get current active user.
    Can be extended to check if user is active/enabled.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current active user
    """
    # Add additional checks here if needed (e.g., is_active flag)
    return current_user


def require_role(required_role: UserRole):
    """
    Dependency factory to require a specific role or higher.
    
    Args:
        required_role: Minimum required role
        
    Returns:
        Dependency function that checks user role
    """
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        if not current_user.has_permission(required_role):
            logger.warning(
                f"Access denied for user {current_user.email} "
                f"(role: {current_user.role}, required: {required_role})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}"
            )
        return current_user
    
    return role_checker


# Convenience dependencies for common role checks
require_student = require_role(UserRole.STUDENT)
require_faculty = require_role(UserRole.FACULTY)
require_admin = require_role(UserRole.ADMIN)
