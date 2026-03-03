from fastapi import APIRouter
from .auth import router as auth_router
from .users import router as users_router
from .subjects import router as subjects_router
from .units import router as units_router
from .topics import router as topics_router
from .concepts import router as concepts_router
from .agents import router as agents_router
from .question_banks import router as question_banks_router
from .patterns import router as patterns_router
from .papers import router as papers_router
from .answer_keys import router as answer_keys_router
from .evaluations import router as evaluations_router
from .performance import router as performance_router
from .roadmap import router as roadmap_router

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(subjects_router, prefix="/subjects", tags=["Subjects"])
api_router.include_router(units_router, prefix="/units", tags=["Units"])
api_router.include_router(topics_router, prefix="/topics", tags=["Topics"])
api_router.include_router(concepts_router, prefix="/concepts", tags=["Concepts"])
api_router.include_router(agents_router, prefix="/agents", tags=["Agents"])
api_router.include_router(question_banks_router, prefix="/question-banks", tags=["Question Banks"])
api_router.include_router(patterns_router, prefix="/patterns", tags=["Patterns"])
api_router.include_router(papers_router, prefix="/papers", tags=["Papers"])
api_router.include_router(answer_keys_router, prefix="/answer-keys", tags=["Answer Keys"])
api_router.include_router(evaluations_router, prefix="/evaluations", tags=["Evaluations"])
api_router.include_router(performance_router, prefix="/performance", tags=["Performance"])
api_router.include_router(roadmap_router, prefix="/roadmap", tags=["Roadmap"])

__all__ = ["api_router"]
