import os
import io
import pickle
import sys
from pathlib import Path

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials as OAuth2Credentials
    from google.auth.oauthlib.flow import InstalledAppFlow
except ImportError as e:
    print(f"Google libraries not available: {e}")
    print(f"Video will not be upload to Google Drive")
    GOOGLE_LIBS_AVAILABLE = False

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    """Initialize Google Drive service using OAuth2"""
    if not GOOGLE_LIBS_AVAILABLE:
        print("Google libraries not available")
        return None

    try:
        creds = None
        
        # Load existing credentials
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds_file = 'oauth_credentials.json'
                if not os.path.exists(creds_file):
                    print(f"⚠️ Warning: {creds_file} not found!")
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=8888)
            
            # Save credentials
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        service = build('drive', 'v3', credentials=creds)
        print("✅ Google Drive service initialized")
        return service
        
    except Exception as e:
        print(f"❌ Error initializing Google Drive: {e}")
        return None


def upload_to_drive(file_content, filename, folder_id=None):
    """Upload file to Google Drive"""
    if not GOOGLE_LIBS_AVAILABLE:
        print("❌ Google libraries not available for upload")
        return None
    
    try:
        service = get_drive_service()
        if not service:
            print("❌ Google Drive service not available")
            return None

        # Use provided folder or get from environment
        final_folder_id = folder_id or os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        
        file_metadata = {'name': filename}
        
        if final_folder_id:
            file_metadata['parents'] = [final_folder_id]

        # Prepare file for upload
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='video/webm')
        
        # Upload file
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        print(f"✅ File uploaded to Google Drive: {file.get('id')}")
        return {
            'id': file.get('id'),
            'webViewLink': file.get('webViewLink')
        }
    
    except Exception as e:
        print(f"❌ Error uploading to Google Drive: {e}")
        return None


def create_drive_folder(folder_name, parent_folder_id=None):
    """Create a folder in Google Drive"""
    if not GOOGLE_LIBS_AVAILABLE:
        return None

    try:
        service = get_drive_service()
        if not service:
            return None

        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        folder = service.files().create(body=file_metadata, fields='id').execute()
        print(f"✅ Folder created: {folder.get('id')}")
        return folder.get('id')
    
    except Exception as e:
        print(f"❌ Error creating folder: {e}")
        return None