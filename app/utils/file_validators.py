import magic
from fastapi import UploadFile, HTTPException

MAX_FILE_SIZE_MB = 5
MAX_LOGO_SIZE_MB = 2

ALLOWED_RESUME_MIMES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
ALLOWED_IMAGE_MIMES = ['image/jpeg', 'image/png', 'image/jpg']

async def validate_resume_file(file: UploadFile) -> bytes:
    """Validate resume file size and type"""
    # Check file extension
    if not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are allowed")
    
    # Read file content
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    
    # Check size
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB")
    
    # Verify MIME type using magic bytes
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_RESUME_MIMES:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {mime}. Only PDF and DOCX allowed.")
    
    return content

async def validate_image_file(file: UploadFile) -> bytes:
    """Validate image file size and type"""
    # Check file extension
    if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(status_code=400, detail="Only JPG, JPEG, and PNG images are allowed")
    
    # Read file content
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    
    # Check size
    if file_size_mb > MAX_LOGO_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"Image too large. Maximum size is {MAX_LOGO_SIZE_MB}MB")
    
    # Verify MIME type
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(status_code=400, detail=f"Invalid image type: {mime}")
    
    return content
