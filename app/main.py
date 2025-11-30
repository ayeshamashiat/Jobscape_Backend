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

@app.get("/")
def root():
    return {"message": "Jobscape backend is running!"}

@app.get("/supabase-test")
def supabase_test():
    try:
        buckets = supabase.storage.list_buckets()
        return {"status": "connected", "buckets": [b.name for b in buckets]}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
