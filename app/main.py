from fastapi import FastAPI
from app.database import Base, engine
from app.models import user
from supabase import create_client
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Jobscape Backend")

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

<<<<<<< Updated upstream
@app.get("/")
=======
# Create scheduler
scheduler = BackgroundScheduler()


# ===== LIFESPAN EVENT HANDLER (REPLACES @app.on_event) =====
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
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan  # ← ADD THIS
)


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
>>>>>>> Stashed changes
def root():
    return {"message": "Jobscape backend is running!"}

@app.get("/supabase-test")
def supabase_test():
    try:
        buckets = supabase.storage.list_buckets()
        return {"status": "connected", "buckets": [b.name for b in buckets]}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
