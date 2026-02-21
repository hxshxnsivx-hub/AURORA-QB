from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db, close_db
from api import api_router
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting AURORA Assess API...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down AURORA Assess API...")
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title="AURORA Assess API",
    description="""
    ## Multi-agent exam generation and evaluation system
    
    AURORA Assess provides intelligent exam paper generation, automated evaluation,
    and personalized learning recommendations.
    
    ### Features
    
    * **Authentication**: JWT-based authentication with role-based access control
    * **Question Banks**: Upload and manage question banks with AI-powered tagging
    * **Paper Generation**: Generate multiple exam paper sets following learned patterns
    * **Automated Grading**: Hybrid rule-based and LLM-powered evaluation
    * **Performance Analysis**: Track student performance and identify weaknesses
    * **Roadmap Integration**: Update personalized learning paths based on performance
    
    ### Roles
    
    * **Student**: Attempt exams, view performance, access resources
    * **Faculty**: Create content, generate papers, review grading
    * **Admin**: Manage users, system configuration
    
    ### Authentication
    
    Most endpoints require authentication. Include the JWT token in the Authorization header:
    
    ```
    Authorization: Bearer <your_token>
    ```
    
    Get your token by calling `/api/auth/login` or `/api/auth/register`.
    """,
    version="0.1.0",
    lifespan=lifespan,
    contact={
        "name": "AURORA Assess Team",
        "email": "support@aurora-assess.example.com",
    },
    license_info={
        "name": "MIT",
    },
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "message": "AURORA Assess API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}
