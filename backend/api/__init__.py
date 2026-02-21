from fastapi import APIRouter
from .auth import router as auth_router
from .users import router as users_router
from .subjects import router as subjects_router
from .units import router as units_router
from .topics import router as topics_router
from .concepts import router as concepts_router
from .agents import router as agents_router

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(subjects_router, prefix="/subjects", tags=["Subjects"])
api_router.include_router(units_router, prefix="/units", tags=["Units"])
api_router.include_router(topics_router, prefix="/topics", tags=["Topics"])
api_router.include_router(concepts_router, prefix="/concepts", tags=["Concepts"])
api_router.include_router(agents_router, prefix="/agents", tags=["Agents"])

__all__ = ["api_router"]
