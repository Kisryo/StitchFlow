"""
Google Sheets Integration Component.

Handles syncing workflow data to Google Sheets for human review and editing.
"""
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from datetime import datetime

from config.settings import settings
from models import Entity, Recommendation


class GoogleSheetsClient:
    """
    Client for interacting with Google Sheets API.
    
    Supports OAuth2 authentication and service account authentication.
    """
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Google Sheets client.
        
        Args:
            credentials_path: Path to service account credentials JSON file
        """
        self.credentials_path = credentials_path or settings.google_credentials_path
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Sheets API service with authentication."""
        try:
            # Use service account authentication
            if os.path.exists(self.credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                self.service = build('sheets', 'v4', credentials=credentials)
                print(f"[Google Sheets] Initialized with service account: {self.credentials_path}")
            else:
                print(f"[Google Sheets] Warning: Credentials file not found at {self.credentials_path}")
                print("[Google Sheets] Google Sheets integration will not be available")
                self.service = None
        except Exception as e:
            print(f"[Google Sheets] Error initializing service: {str(e)}")
            self.service = None
    
    def is_available(self) -> bool:
        """Check if Google Sheets service is available."""
        return self.service is not None
    
    def create_spreadsheet(self, title: str) -> Optional[str]:
        """
        Create a new Google Spreadsheet.
        
        Args:
            title: Title for the new spreadsheet
            
        Returns:
            Spreadsheet ID if successful, None otherwise
        """
        if not self.is_available():
            print("[Google Sheets] Service not available")
            return None
        
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            result = self.service.spreadsheets().create(body=spreadsheet).execute()
            spreadsheet_id = result.get('spreadsheetId')
            print(f"[Google Sheets] Created spreadsheet: {spreadsheet_id}")
            return spreadsheet_id
        except HttpError as e:
            print(f"[Google Sheets] Error creating spreadsheet: {str(e)}")
            return None
    
    def write_data(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = 'USER_ENTERED'
    ) -> bool:
        """
        Write data to a Google Sheet.
        
        Args:
            spreadsheet_id: ID of the spreadsheet
            range_name: A1 notation range (e.g., 'Sheet1!A1:D10')
            values: 2D array of values to write
            value_input_option: How to interpret input ('RAW' or 'USER_ENTERED')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            print("[Google Sheets] Service not available")
            return False
        
        try:
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body
            ).execute()
            
            updated_cells = result.get('updatedCells', 0)
            print(f"[Google Sheets] Updated {updated_cells} cells in {range_name}")
            return True
        except HttpError as e:
            print(f"[Google Sheets] Error writing data: {str(e)}")
            return False
    
    def read_data(
        self,
        spreadsheet_id: str,
        range_name: str
    ) -> Optional[List[List[Any]]]:
        """
        Read data from a Google Sheet.
        
        Args:
            spreadsheet_id: ID of the spreadsheet
            range_name: A1 notation range (e.g., 'Sheet1!A1:D10')
            
        Returns:
            2D array of values if successful, None otherwise
        """
        if not self.is_available():
            print("[Google Sheets] Service not available")
            return None
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            print(f"[Google Sheets] Read {len(values)} rows from {range_name}")
            return values
        except HttpError as e:
            print(f"[Google Sheets] Error reading data: {str(e)}")
            return None
    
    def append_data(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = 'USER_ENTERED'
    ) -> bool:
        """
        Append data to a Google Sheet.
        
        Args:
            spreadsheet_id: ID of the spreadsheet
            range_name: A1 notation range (e.g., 'Sheet1!A1')
            values: 2D array of values to append
            value_input_option: How to interpret input ('RAW' or 'USER_ENTERED')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            print("[Google Sheets] Service not available")
            return False
        
        try:
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body
            ).execute()
            
            updated_cells = result.get('updates', {}).get('updatedCells', 0)
            print(f"[Google Sheets] Appended {updated_cells} cells to {range_name}")
            return True
        except HttpError as e:
            print(f"[Google Sheets] Error appending data: {str(e)}")
            return False


# ============================================================================
# Workflow-Specific Functions
# ============================================================================

def format_entities_for_sheets(entities: List[Entity]) -> List[List[str]]:
    """
    Format extracted entities for Google Sheets.
    
    Args:
        entities: List of Entity objects
        
    Returns:
        2D array with headers and entity data
    """
    # Header row
    data = [['Entity Type', 'Value', 'Confidence', 'Context']]
    
    # Entity rows
    for entity in entities:
        data.append([
            entity.entity_type,
            entity.value,
            f"{entity.confidence:.2f}",
            entity.context or ""
        ])
    
    return data


def format_recommendations_for_sheets(recommendations: List[Recommendation]) -> List[List[str]]:
    """
    Format recommendations for Google Sheets.
    
    Args:
        recommendations: List of Recommendation objects
        
    Returns:
        2D array with headers and recommendation data
    """
    # Header row
    data = [['ID', 'Action Type', 'Description', 'Confidence', 'Priority', 'Status']]
    
    # Recommendation rows
    for rec in recommendations:
        data.append([
            rec.recommendation_id,
            rec.action_type,
            rec.description,
            f"{rec.confidence:.2f}",
            rec.priority,
            'Pending'  # Default status
        ])
    
    return data


async def sync_to_sheets(
    workflow_id: str,
    entities: List[Entity],
    recommendations: List[Recommendation],
    spreadsheet_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sync workflow data to Google Sheets.
    
    Creates a new spreadsheet or updates existing one with:
    - Extracted entities
    - Generated recommendations
    
    Args:
        workflow_id: Workflow identifier
        entities: List of extracted entities
        recommendations: List of recommendations
        spreadsheet_id: Optional existing spreadsheet ID
        
    Returns:
        Result with spreadsheet ID and sync status
    """
    client = GoogleSheetsClient()
    
    if not client.is_available():
        return {
            "success": False,
            "error": "Google Sheets service not available. Check credentials configuration.",
            "spreadsheet_id": None
        }
    
    try:
        # Create new spreadsheet if not provided
        if not spreadsheet_id:
            title = f"StitchFlow Workflow - {workflow_id}"
            spreadsheet_id = client.create_spreadsheet(title)
            if not spreadsheet_id:
                return {
                    "success": False,
                    "error": "Failed to create spreadsheet",
                    "spreadsheet_id": None
                }
        
        # Format data
        entities_data = format_entities_for_sheets(entities)
        recommendations_data = format_recommendations_for_sheets(recommendations)
        
        # Write entities to Sheet1
        entities_success = client.write_data(
            spreadsheet_id=spreadsheet_id,
            range_name='Entities!A1',
            values=entities_data
        )
        
        # Write recommendations to Sheet2
        recommendations_success = client.write_data(
            spreadsheet_id=spreadsheet_id,
            range_name='Recommendations!A1',
            values=recommendations_data
        )
        
        if entities_success and recommendations_success:
            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            return {
                "success": True,
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_url": spreadsheet_url,
                "entities_synced": len(entities),
                "recommendations_synced": len(recommendations)
            }
        else:
            return {
                "success": False,
                "error": "Failed to write data to sheets",
                "spreadsheet_id": spreadsheet_id
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Sync failed: {str(e)}",
            "spreadsheet_id": spreadsheet_id
        }


async def read_sheet_updates(
    spreadsheet_id: str,
    sheet_name: str = 'Recommendations'
) -> Optional[List[Dict[str, Any]]]:
    """
    Read updates from Google Sheets (bidirectional sync).
    
    Reads the recommendations sheet to detect manual edits by users.
    
    Args:
        spreadsheet_id: ID of the spreadsheet
        sheet_name: Name of the sheet to read
        
    Returns:
        List of updated recommendations or None if failed
    """
    client = GoogleSheetsClient()
    
    if not client.is_available():
        print("[Google Sheets] Service not available for reading updates")
        return None
    
    try:
        # Read data from sheet
        range_name = f"{sheet_name}!A1:F100"  # Read up to 100 rows
        values = client.read_data(spreadsheet_id, range_name)
        
        if not values or len(values) < 2:
            print("[Google Sheets] No data found in sheet")
            return []
        
        # Parse data (skip header row)
        headers = values[0]
        recommendations = []
        
        for row in values[1:]:
            if len(row) >= 6:  # Ensure row has all columns
                recommendations.append({
                    'recommendation_id': row[0],
                    'action_type': row[1],
                    'description': row[2],
                    'confidence': float(row[3]) if row[3] else 0.0,
                    'priority': row[4],
                    'status': row[5]  # User can edit this column
                })
        
        return recommendations
    
    except Exception as e:
        print(f"[Google Sheets] Error reading updates: {str(e)}")
        return None
