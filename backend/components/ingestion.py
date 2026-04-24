"""
Document ingestion component.

Handles file upload, text extraction from various formats, and workflow state updates.
"""
import os
import time
from typing import Optional
from sqlalchemy.orm import Session
import PyPDF2
import docx
import email
from email import policy

from models import IngestionResult, DocumentMetadata
from database.utils import get_workflow, log_audit_entry
from models import WorkflowState


async def ingest_document(
    workflow_id: str,
    file_path: str,
    file_type: str,
    db: Session
) -> IngestionResult:
    """
    Ingest a document and extract text content.
    
    Args:
        workflow_id: Unique workflow identifier
        file_path: Path to uploaded file
        file_type: File type (pdf, docx, txt, email)
        db: Database session
        
    Returns:
        IngestionResult with extracted text and metadata
        
    Raises:
        ValueError: If file type is not supported
        Exception: If text extraction fails
    """
    start_time = time.time()
    
    try:
        # Extract text based on file type
        extracted_text = extract_text(file_path, file_type)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Calculate extraction time
        extraction_time = time.time() - start_time
        
        # Create ingestion result
        result = IngestionResult(
            workflow_id=workflow_id,
            extracted_text=extracted_text,
            file_type=file_type,
            file_size=file_size,
            extraction_time=extraction_time,
            success=True,
            error=None
        )
        
        # Update workflow in database
        workflow = get_workflow(db, workflow_id)
        if workflow:
            workflow.document_path = file_path
            workflow.document_text = extracted_text
            workflow.state = WorkflowState.INGESTED.value
            
            # Create document metadata
            metadata = DocumentMetadata(
                filename=os.path.basename(file_path),
                file_type=file_type,
                file_size=file_size,
                word_count=len(extracted_text.split())
            )
            # Use mode='json' to serialize datetime objects to ISO format strings
            workflow.workflow_metadata = metadata.model_dump(mode='json')
            
            # Commit changes
            db.commit()
            db.refresh(workflow)
            
            # Log audit entry
            log_audit_entry(
                db=db,
                workflow_id=workflow_id,
                action_type="state_transition",
                actor="system",
                details={
                    "from_state": "New",
                    "to_state": "Ingested",
                    "reason": "Document uploaded and text extracted successfully"
                }
            )
        
        return result
        
    except Exception as e:
        # Log error and update workflow to Failed state
        extraction_time = time.time() - start_time
        
        result = IngestionResult(
            workflow_id=workflow_id,
            extracted_text="",
            file_type=file_type,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            extraction_time=extraction_time,
            success=False,
            error=str(e)
        )
        
        # Update workflow to Failed state
        workflow = get_workflow(db, workflow_id)
        if workflow:
            workflow.state = WorkflowState.FAILED.value
            db.commit()
            
            # Log audit entry
            log_audit_entry(
                db=db,
                workflow_id=workflow_id,
                action_type="state_transition",
                actor="system",
                details={
                    "from_state": workflow.state,
                    "to_state": "Failed",
                    "reason": f"Text extraction failed: {str(e)}"
                }
            )
        
        raise Exception(f"Text extraction failed: {str(e)}")


def extract_text(file_path: str, file_type: str) -> str:
    """
    Extract text from file based on type.
    
    Args:
        file_path: Path to file
        file_type: File type (pdf, docx, txt, email)
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If file type is not supported
        Exception: If extraction fails
    """
    file_type = file_type.lower()
    
    if file_type == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_type == 'docx':
        return extract_text_from_docx(file_path)
    elif file_type == 'txt':
        return extract_text_from_txt(file_path)
    elif file_type in ['email', 'eml']:
        return extract_text_from_email(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF file.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Extracted text content
    """
    try:
        text_content = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from each page
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text:
                    text_content.append(text)
        
        return "\n\n".join(text_content)
        
    except Exception as e:
        raise Exception(f"PDF extraction failed: {str(e)}")


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from DOCX file.
    
    Args:
        file_path: Path to DOCX file
        
    Returns:
        Extracted text content
    """
    try:
        doc = docx.Document(file_path)
        
        # Extract text from paragraphs
        text_content = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text)
        
        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_content.append(cell.text)
        
        return "\n\n".join(text_content)
        
    except Exception as e:
        raise Exception(f"DOCX extraction failed: {str(e)}")


def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text from TXT file.
    
    Args:
        file_path: Path to TXT file
        
    Returns:
        Extracted text content
    """
    try:
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, read as binary and decode with errors='ignore'
        with open(file_path, 'rb') as file:
            return file.read().decode('utf-8', errors='ignore')
            
    except Exception as e:
        raise Exception(f"TXT extraction failed: {str(e)}")


def extract_text_from_email(file_path: str) -> str:
    """
    Extract text from email file (.eml).
    
    Args:
        file_path: Path to email file
        
    Returns:
        Extracted text content including subject, from, to, and body
    """
    try:
        with open(file_path, 'rb') as file:
            msg = email.message_from_binary_file(file, policy=policy.default)
        
        # Extract email metadata
        text_parts = []
        
        # Subject
        subject = msg.get('Subject', '')
        if subject:
            text_parts.append(f"Subject: {subject}")
        
        # From
        from_addr = msg.get('From', '')
        if from_addr:
            text_parts.append(f"From: {from_addr}")
        
        # To
        to_addr = msg.get('To', '')
        if to_addr:
            text_parts.append(f"To: {to_addr}")
        
        # Date
        date = msg.get('Date', '')
        if date:
            text_parts.append(f"Date: {date}")
        
        text_parts.append("")  # Empty line separator
        
        # Extract email body
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        body = part.get_content()
                        text_parts.append(body)
                    except:
                        pass
        else:
            try:
                body = msg.get_content()
                text_parts.append(body)
            except:
                pass
        
        return "\n".join(text_parts)
        
    except Exception as e:
        raise Exception(f"Email extraction failed: {str(e)}")
