"""
Document processing models.

Models for document ingestion, text extraction, and PII redaction.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from datetime import datetime


class IngestionResult(BaseModel):
    """
    Result of document ingestion and text extraction.
    
    Returned after a document is uploaded and processed.
    """
    workflow_id: str = Field(..., description="Associated workflow ID")
    extracted_text: str = Field(..., description="Extracted text content from document")
    file_type: str = Field(..., description="Document file type (pdf, docx, txt, email)")
    file_size: int = Field(..., description="File size in bytes")
    extraction_time: float = Field(..., description="Time taken for extraction in seconds")
    success: bool = Field(default=True, description="Whether extraction succeeded")
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    
    @field_validator('file_type')
    @classmethod
    def validate_file_type(cls, v: str) -> str:
        """Validate file type is supported."""
        supported_types = {'pdf', 'docx', 'txt', 'email', 'eml'}
        if v.lower() not in supported_types:
            raise ValueError(f"Unsupported file type: {v}. Supported: {supported_types}")
        return v.lower()
    
    @field_validator('file_size')
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        """Validate file size is within limits."""
        max_size = 10 * 1024 * 1024  # 10 MB
        if v > max_size:
            raise ValueError(f"File size {v} exceeds maximum {max_size} bytes")
        if v <= 0:
            raise ValueError("File size must be positive")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "extracted_text": "This is the extracted document content...",
                "file_type": "pdf",
                "file_size": 1024000,
                "extraction_time": 0.5,
                "success": True,
                "error": None
            }
        }


class PIIMatch(BaseModel):
    """
    Represents a detected PII (Personally Identifiable Information) match.
    
    Used during PII redaction to track what was found and masked.
    """
    pii_type: Literal["name", "email", "phone", "address", "ssn"] = Field(
        ...,
        description="Type of PII detected"
    )
    original_value: str = Field(..., description="Original PII value before masking")
    masked_token: str = Field(..., description="Masked token (e.g., [EMAIL], [PHONE])")
    start_pos: int = Field(..., description="Start position in original text")
    end_pos: int = Field(..., description="End position in original text")
    
    @field_validator('start_pos', 'end_pos')
    @classmethod
    def validate_positions(cls, v: int) -> int:
        """Validate positions are non-negative."""
        if v < 0:
            raise ValueError("Position must be non-negative")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "pii_type": "email",
                "original_value": "john.doe@example.com",
                "masked_token": "[EMAIL_1]",
                "start_pos": 45,
                "end_pos": 66
            }
        }


class RedactionResult(BaseModel):
    """
    Result of PII redaction process.
    
    Contains both original and redacted text, plus mapping for restoration.
    """
    workflow_id: str = Field(..., description="Associated workflow ID")
    original_text: str = Field(..., description="Original text before redaction")
    redacted_text: str = Field(..., description="Text with PII masked")
    token_map: dict[str, str] = Field(
        ...,
        description="Mapping from masked tokens to original values"
    )
    pii_matches: List[PIIMatch] = Field(
        default_factory=list,
        description="List of all PII matches found"
    )
    redaction_time: float = Field(..., description="Time taken for redaction in seconds")
    
    @field_validator('token_map')
    @classmethod
    def validate_token_map(cls, v: dict) -> dict:
        """Validate token map has proper format."""
        for key, value in v.items():
            if not key.startswith('[') or not key.endswith(']'):
                raise ValueError(f"Token key must be in format [TOKEN]: {key}")
            if not isinstance(value, str):
                raise ValueError(f"Token value must be string: {value}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "original_text": "Contact John Doe at john.doe@example.com or 555-1234",
                "redacted_text": "Contact [NAME_1] at [EMAIL_1] or [PHONE_1]",
                "token_map": {
                    "[NAME_1]": "John Doe",
                    "[EMAIL_1]": "john.doe@example.com",
                    "[PHONE_1]": "555-1234"
                },
                "pii_matches": [
                    {
                        "pii_type": "name",
                        "original_value": "John Doe",
                        "masked_token": "[NAME_1]",
                        "start_pos": 8,
                        "end_pos": 16
                    }
                ],
                "redaction_time": 0.1
            }
        }


class DocumentMetadata(BaseModel):
    """
    Metadata about an uploaded document.
    
    Stored in workflow.metadata field.
    """
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type/extension")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    upload_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When file was uploaded"
    )
    page_count: Optional[int] = Field(None, description="Number of pages (for PDFs)")
    word_count: Optional[int] = Field(None, description="Approximate word count")
    
    class Config:
        json_schema_extra = {
            "example": {
                "filename": "contract.pdf",
                "file_type": "pdf",
                "file_size": 1024000,
                "mime_type": "application/pdf",
                "upload_timestamp": "2024-01-01T00:00:00Z",
                "page_count": 5,
                "word_count": 1500
            }
        }
