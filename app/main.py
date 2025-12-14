from fastapi import FastAPI
from app.database import Base, engine
from app.models import user
from app.utils.cloudinary_client import init_cloudinary
from app.routes import auth_routes
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Jobscape Backend")
init_cloudinary()

@app.get("/")
def root():
    return {"message": "Jobscape backend is running!"}

app.include_router(auth_routes.router)


