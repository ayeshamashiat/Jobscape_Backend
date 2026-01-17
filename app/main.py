from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import Base, engine
from app.models import user, job_seeker, employer, job, resume, password_reset
from app.utils.cloudinary_client import init_cloudinary
from app.routes import auth_routes, employer_routes, job_routes, resume_routes

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI(
    title="Jobscape Backend API",
    description="Job posting platform for Bangladesh IT sector",
    version="1.0.0"
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://your-frontend-domain.com"  # Add your production frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Cloudinary
init_cloudinary()

# Health check
@app.get("/", tags=["health"])
def root():
    return {
        "message": "Jobscape Backend API is running!",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "healthy"}

# Include routers
app.include_router(auth_routes.router)
app.include_router(employer_routes.router)
app.include_router(job_routes.router)
app.include_router(resume_routes.router)
