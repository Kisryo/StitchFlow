"""
Gmail Integration Component.

Handles creating and managing Gmail drafts for workflow recommendations.
"""
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

from config.settings import settings
from models import Recommendation


class GmailClient:
    """
    Client for interacting with Gmail API.
    
    Supports creating drafts, sending emails, and managing draft lifecycle.
    """
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Gmail client.
        
        Args:
            credentials_path: Path to service account credentials JSON file
        """
        self.credentials_path = credentials_path or settings.google_credentials_path
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Gmail API service with authentication."""
        try:
            # Use service account authentication
            if os.path.exists(self.credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=[
                        'https://www.googleapis.com/auth/gmail.compose',
                        'https://www.googleapis.com/auth/gmail.modify'
                    ]
                )
                self.service = build('gmail', 'v1', credentials=credentials)
                print(f"[Gmail] Initialized with service account: {self.credentials_path}")
            else:
                print(f"[Gmail] Warning: Credentials file not found at {self.credentials_path}")
                print("[Gmail] Gmail integration will not be available")
                self.service = None
        except Exception as e:
            print(f"[Gmail] Error initializing service: {str(e)}")
            self.service = None
    
    def is_available(self) -> bool:
        """Check if Gmail service is available."""
        return self.service is not None
    
    def create_message(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an email message.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            from_email: Sender email (optional)
            
        Returns:
            Message dict ready for Gmail API
        """
        message = MIMEMultipart('alternative')
        message['To'] = to
        message['Subject'] = subject
        if from_email:
            message['From'] = from_email
        
        # Add body as both plain text and HTML
        text_part = MIMEText(body, 'plain')
        html_part = MIMEText(body, 'html')
        message.attach(text_part)
        message.attach(html_part)
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw_message}
    
    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        user_id: str = 'me'
    ) -> Optional[str]:
        """
        Create a Gmail draft.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            from_email: Sender email (optional)
            user_id: Gmail user ID (default: 'me')
            
        Returns:
            Draft ID if successful, None otherwise
        """
        if not self.is_available():
            print("[Gmail] Service not available")
            return None
        
        try:
            message = self.create_message(to, subject, body, from_email)
            draft = {'message': message}
            
            result = self.service.users().drafts().create(
                userId=user_id,
                body=draft
            ).execute()
            
            draft_id = result.get('id')
            print(f"[Gmail] Created draft: {draft_id}")
            return draft_id
        except HttpError as e:
            print(f"[Gmail] Error creating draft: {str(e)}")
            return None
    
    def get_draft(self, draft_id: str, user_id: str = 'me') -> Optional[Dict[str, Any]]:
        """
        Get a Gmail draft by ID.
        
        Args:
            draft_id: Draft ID
            user_id: Gmail user ID (default: 'me')
            
        Returns:
            Draft details if successful, None otherwise
        """
        if not self.is_available():
            print("[Gmail] Service not available")
            return None
        
        try:
            draft = self.service.users().drafts().get(
                userId=user_id,
                id=draft_id
            ).execute()
            
            print(f"[Gmail] Retrieved draft: {draft_id}")
            return draft
        except HttpError as e:
            print(f"[Gmail] Error getting draft: {str(e)}")
            return None
    
    def send_draft(self, draft_id: str, user_id: str = 'me') -> bool:
        """
        Send a Gmail draft.
        
        Args:
            draft_id: Draft ID
            user_id: Gmail user ID (default: 'me')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            print("[Gmail] Service not available")
            return False
        
        try:
            result = self.service.users().drafts().send(
                userId=user_id,
                body={'id': draft_id}
            ).execute()
            
            message_id = result.get('id')
            print(f"[Gmail] Sent draft {draft_id} as message {message_id}")
            return True
        except HttpError as e:
            print(f"[Gmail] Error sending draft: {str(e)}")
            return False
    
    def delete_draft(self, draft_id: str, user_id: str = 'me') -> bool:
        """
        Delete a Gmail draft.
        
        Args:
            draft_id: Draft ID
            user_id: Gmail user ID (default: 'me')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            print("[Gmail] Service not available")
            return False
        
        try:
            self.service.users().drafts().delete(
                userId=user_id,
                id=draft_id
            ).execute()
            
            print(f"[Gmail] Deleted draft: {draft_id}")
            return True
        except HttpError as e:
            print(f"[Gmail] Error deleting draft: {str(e)}")
            return False
    
    def update_draft(
        self,
        draft_id: str,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        user_id: str = 'me'
    ) -> bool:
        """
        Update an existing Gmail draft.
        
        Args:
            draft_id: Draft ID
            to: Recipient email address
            subject: Email subject
            body: Email body
            from_email: Sender email (optional)
            user_id: Gmail user ID (default: 'me')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            print("[Gmail] Service not available")
            return False
        
        try:
            message = self.create_message(to, subject, body, from_email)
            draft = {'message': message}
            
            self.service.users().drafts().update(
                userId=user_id,
                id=draft_id,
                body=draft
            ).execute()
            
            print(f"[Gmail] Updated draft: {draft_id}")
            return True
        except HttpError as e:
            print(f"[Gmail] Error updating draft: {str(e)}")
            return False


# ============================================================================
# Workflow-Specific Functions
# ============================================================================

def format_recommendations_as_email(
    recommendations: List[Recommendation],
    workflow_id: str,
    document_type: str = "Request"
) -> str:
    """
    Format recommendations as an email body.
    
    Args:
        recommendations: List of Recommendation objects
        workflow_id: Workflow identifier
        document_type: Type of document processed
        
    Returns:
        Formatted email body (HTML)
    """
    # Email header
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
            .recommendation {{ margin: 20px 0; padding: 15px; border-left: 4px solid #007bff; background-color: #f9f9f9; }}
            .priority-high {{ border-left-color: #dc3545; }}
            .priority-medium {{ border-left-color: #ffc107; }}
            .priority-low {{ border-left-color: #28a745; }}
            .confidence {{ color: #666; font-size: 0.9em; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>StitchFlow Workflow Recommendations</h2>
            <p><strong>Workflow ID:</strong> {workflow_id}</p>
            <p><strong>Document Type:</strong> {document_type}</p>
            <p><strong>Total Recommendations:</strong> {len(recommendations)}</p>
        </div>
    """
    
    # Group recommendations by priority
    high_priority = [r for r in recommendations if r.priority == 'high']
    medium_priority = [r for r in recommendations if r.priority == 'medium']
    low_priority = [r for r in recommendations if r.priority == 'low']
    
    # Add high priority recommendations
    if high_priority:
        html += "<h3>🔴 High Priority Actions</h3>"
        for rec in high_priority:
            html += f"""
            <div class="recommendation priority-high">
                <h4>{rec.action_type}</h4>
                <p>{rec.description}</p>
                <p class="confidence">Confidence: {rec.confidence:.0%}</p>
                {f'<p><em>Reasoning: {rec.reasoning}</em></p>' if rec.reasoning else ''}
            </div>
            """
    
    # Add medium priority recommendations
    if medium_priority:
        html += "<h3>🟡 Medium Priority Actions</h3>"
        for rec in medium_priority:
            html += f"""
            <div class="recommendation priority-medium">
                <h4>{rec.action_type}</h4>
                <p>{rec.description}</p>
                <p class="confidence">Confidence: {rec.confidence:.0%}</p>
                {f'<p><em>Reasoning: {rec.reasoning}</em></p>' if rec.reasoning else ''}
            </div>
            """
    
    # Add low priority recommendations
    if low_priority:
        html += "<h3>🟢 Low Priority Actions</h3>"
        for rec in low_priority:
            html += f"""
            <div class="recommendation priority-low">
                <h4>{rec.action_type}</h4>
                <p>{rec.description}</p>
                <p class="confidence">Confidence: {rec.confidence:.0%}</p>
                {f'<p><em>Reasoning: {rec.reasoning}</em></p>' if rec.reasoning else ''}
            </div>
            """
    
    # Email footer
    html += """
        <div class="footer">
            <p>This email was automatically generated by StitchFlow V2.</p>
            <p>Please review these recommendations and take appropriate action.</p>
        </div>
    </body>
    </html>
    """
    
    return html


async def create_gmail_draft(
    workflow_id: str,
    recommendations: List[Recommendation],
    recipient_email: str,
    document_type: str = "Request",
    subject: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a Gmail draft with workflow recommendations.
    
    Args:
        workflow_id: Workflow identifier
        recommendations: List of recommendations
        recipient_email: Email address to send to
        document_type: Type of document processed
        subject: Optional custom subject line
        
    Returns:
        Result with draft ID and status
    """
    client = GmailClient()
    
    if not client.is_available():
        return {
            "success": False,
            "error": "Gmail service not available. Check credentials configuration.",
            "draft_id": None
        }
    
    try:
        # Generate subject if not provided
        if not subject:
            subject = f"StitchFlow Recommendations - {document_type} ({workflow_id[:8]})"
        
        # Format email body
        body = format_recommendations_as_email(recommendations, workflow_id, document_type)
        
        # Create draft
        draft_id = client.create_draft(
            to=recipient_email,
            subject=subject,
            body=body
        )
        
        if draft_id:
            return {
                "success": True,
                "draft_id": draft_id,
                "recipient": recipient_email,
                "recommendations_count": len(recommendations)
            }
        else:
            return {
                "success": False,
                "error": "Failed to create draft",
                "draft_id": None
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Draft creation failed: {str(e)}",
            "draft_id": None
        }


async def approve_and_send_draft(draft_id: str) -> Dict[str, Any]:
    """
    Approve and send a Gmail draft.
    
    Args:
        draft_id: Draft ID to send
        
    Returns:
        Result with send status
    """
    client = GmailClient()
    
    if not client.is_available():
        return {
            "success": False,
            "error": "Gmail service not available"
        }
    
    try:
        success = client.send_draft(draft_id)
        
        if success:
            return {
                "success": True,
                "draft_id": draft_id,
                "status": "sent"
            }
        else:
            return {
                "success": False,
                "error": "Failed to send draft"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Send failed: {str(e)}"
        }


async def reject_and_delete_draft(draft_id: str) -> Dict[str, Any]:
    """
    Reject and delete a Gmail draft.
    
    Args:
        draft_id: Draft ID to delete
        
    Returns:
        Result with deletion status
    """
    client = GmailClient()
    
    if not client.is_available():
        return {
            "success": False,
            "error": "Gmail service not available"
        }
    
    try:
        success = client.delete_draft(draft_id)
        
        if success:
            return {
                "success": True,
                "draft_id": draft_id,
                "status": "deleted"
            }
        else:
            return {
                "success": False,
                "error": "Failed to delete draft"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Deletion failed: {str(e)}"
        }
