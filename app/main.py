"""
Jobscape FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.openapi.utils import get_openapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import engine, Base
from app.utils.cloudinary_client import init_cloudinary
from app.tasks.job_closure import close_expired_jobs

# ─── Route imports ────────────────────────────────────────────────────────────
from app.routes import (
    admin_routes,
    application_routes,
    auth_routes,
    chat_routes,
    commute_routes,        # ← commute score feature
    cover_letter_routes,
    employer_routes,
    interview_routes,
    job_routes,
    oauth_routes,
    profile_routes,
    resume_routes,
    selection_routes,
    subscription_routes,
    saved_job_routes,
    notification_routes,
    video_routes,
)

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize Cloudinary
init_cloudinary()

# Create scheduler
scheduler = BackgroundScheduler()

# ===== LIFESPAN EVENT HANDLER =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan - handles startup and shutdown events
    This replaces the deprecated @app.on_event decorators
    """
    # STARTUP
    print("🚀 Starting Jobscape Backend API...")
    
    # Start background scheduler for job expiration
    scheduler.add_job(
        close_expired_jobs,
        'interval',
        hours=1,  # Run every hour
        id='close_expired_jobs',
        replace_existing=True
    )
    scheduler.start()
    print("✅ Background scheduler started - checking job deadlines every hour")
    
    yield  # Application is running
    
    # SHUTDOWN
    print("🛑 Shutting down Jobscape Backend API...")
    scheduler.shutdown()
    print("❌ Background scheduler stopped")


# ===== INITIALIZE FASTAPI WITH LIFESPAN =====
app = FastAPI(
    title="Jobscape Backend API",
    description="Job posting platform for Bangladesh IT sector",
    version="1.0.0",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
    },
    lifespan=lifespan
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
        "https://jobscape.com",
        "https://your-frontend-domain.com",
        "null"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== CUSTOM OPENAPI SCHEMA (FOR SWAGGER AUTH) =====
def custom_openapi():
    """
    Show JWT Bearer lock icon for all protected routes.
    Public routes are tagged with 'public'.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add Bearer token security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token in the format: Bearer <token>"
        }
    }

    # Apply Bearer security globally except for public routes
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue

            tags = operation.get("tags", [])
            if "public" in tags or "health" in tags:
                continue  # Skip public endpoints

            # Only set security if not already set
            if "security" not in operation:
                operation["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Override the default OpenAPI function
app.openapi = custom_openapi


# ===== ROUTES =====

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

# ─── Register routers ─────────────────────────────────────────────────────────
app.include_router(admin_routes.router)
app.include_router(application_routes.router)
app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(chat_routes.direct_messages_router) # Support for direct /messages calls
app.include_router(commute_routes.router)
app.include_router(cover_letter_routes.router)
app.include_router(employer_routes.router)
app.include_router(interview_routes.router)
app.include_router(job_routes.router)
app.include_router(oauth_routes.router)
app.include_router(profile_routes.router)
app.include_router(resume_routes.router)
app.include_router(selection_routes.router)
app.include_router(subscription_routes.router)
app.include_router(saved_job_routes.router)
app.include_router(notification_routes.router)
app.include_router(video_routes.router)