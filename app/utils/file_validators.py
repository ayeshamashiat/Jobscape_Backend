import os
from typing import Optional
from fastapi import UploadFile, HTTPException
from PIL import Image
import io


def _get_file_extension(filename: Optional[str]) -> str:
    """Safely extract file extension"""
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )
    
    ext = os.path.splitext(filename)[1].lower()
    
    if not ext:
        raise HTTPException(
            status_code=400,
            detail="File has no extension"
        )
    
    return ext


async def validate_image_file(file: UploadFile) -> bytes:
    """Validate image uploads (logos)"""
    
    allowed_extensions = [".jpg", ".jpeg", ".png"]
    file_ext = _get_file_extension(file.filename)  # ✅ Uses helper
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: JPG, PNG. Got: {file_ext}"
        )
    
    content = await file.read()
    file_size = len(content)
    
    # Check file size (2MB max)
    max_size = 2 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max 2MB. Your file: {file_size / 1024 / 1024:.2f}MB"
        )
    
    # Validate it's actually an image
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")
    
    return content


async def validate_document_file(file: UploadFile) -> bytes:
    """Validate document uploads (for verification)"""
    
    allowed_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
    file_ext = _get_file_extension(file.filename)  # ✅ Uses helper
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: JPG, PNG, PDF. Got: {file_ext}"
        )
    
    content = await file.read()
    file_size = len(content)
    
    # Check file size (5MB max)
    max_size = 5 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max 5MB. Your file: {file_size / 1024 / 1024:.2f}MB"
        )
    
    # Validate based on type
    if file_ext in [".jpg", ".jpeg", ".png"]:
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")
    
    elif file_ext == ".pdf":
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
    
    return content


async def validate_resume_file(file: UploadFile) -> bytes:
    """Validate resume uploads"""
    
    allowed_extensions = [".pdf", ".doc", ".docx"]
    file_ext = _get_file_extension(file.filename)  # ✅ Uses helper
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: PDF, DOC, DOCX. Got: {file_ext}"
        )
    
    content = await file.read()
    file_size = len(content)
    
    # Check file size (5MB max)
    max_size = 5 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max 5MB. Your file: {file_size / 1024 / 1024:.2f}MB"
        )
    
    # Validate PDF
    if file_ext == ".pdf":
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
    
    # DOCX validation
    elif file_ext == ".docx":
        if not content.startswith(b'PK'):
            raise HTTPException(status_code=400, detail="Invalid DOCX file")
    
    return content
