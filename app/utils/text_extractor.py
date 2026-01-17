import fitz  # PyMuPDF
from docx import Document
import io
from typing import Any


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF bytes"""
    try:
        doc: Any = fitz.open(stream=file_content, filetype="pdf")  # Type hint to suppress warning
        text = ""
        for page in doc:
            text += page.get_text()  # type: ignore  # PyMuPDF type stubs incomplete
        doc.close()
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")


def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX bytes"""
    try:
        doc = Document(io.BytesIO(file_content))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from DOCX: {str(e)}")


def extract_text_from_resume(file_content: bytes, filename: str) -> str:
    """
    Extract text based on file extension
    """
    if filename.lower().endswith('.pdf'):
        return extract_text_from_pdf(file_content)
    elif filename.lower().endswith('.docx'):
        return extract_text_from_docx(file_content)
    else:
        raise ValueError(f"Unsupported file format. Only PDF and DOCX are supported.")
