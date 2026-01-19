# app/schema/response_schema.py
from pydantic import BaseModel

class MessageResponse(BaseModel):
    message: str
