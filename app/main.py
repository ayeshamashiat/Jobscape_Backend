from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.openapi.utils import get_openapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import Base, engine
from app.models import user, job_seeker, employer, job, resume, password_reset
from app.utils.cloudinary_client import init_cloudinary
from app.routes import admin_routes, auth_routes, employer_routes, job_routes, resume_routes, oauth_routes


# Create tables
Base.metadata.create_all(bind=engine)


# Initialize FastAPI
app = FastAPI(
    title="Jobscape Backend API",
    description="Job posting platform for Bangladesh IT sector",
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True}  # ← Keep auth in Swagger after refresh
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
        "https://your-frontend-domain.com",
        "null"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize Cloudinary
init_cloudinary()


# ===== CUSTOM OPENAPI SCHEMA (FOR SWAGGER AUTH) =====
def custom_openapi():
    """
    Custom OpenAPI schema to show auth locks in Swagger UI.
    This makes protected routes display with lock icons.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Jobscape Backend API",
        version="1.0.0",
        description="Job posting platform for Bangladesh IT sector",
        routes=app.routes,
    )
    
    # Add security scheme for JWT Bearer tokens
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token in the format: Bearer <token>"
        }
    }
    
    # Apply security globally to all routes (except public routes)
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            if isinstance(operation, dict) and "tags" in operation:
                # Skip auth for these public endpoints
                if operation.get("tags") and any(
                    tag in ["health", "authentication"] 
                    for tag in operation.get("tags", [])
                ):
                    continue
                
                # Apply security to all other endpoints
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


# Include routers
app.include_router(auth_routes.router)
app.include_router(employer_routes.router)
app.include_router(job_routes.router)
app.include_router(resume_routes.router)
app.include_router(admin_routes.router)
app.include_router(oauth_routes.router)
