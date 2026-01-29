import os
import io
from pathlib import Path

GOOGLE_LIBS_AVAILABLE = True

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.oauth2 import service_account
except ImportError as e:
    print(f"Google libraries not available: {e}")
    print("Video will not be uploaded to Google Drive")
    GOOGLE_LIBS_AVAILABLE = False


SCOPES = ['https://www.googleapis.com/auth/drive.file']


def get_drive_service():
    """Initialize Google Drive service using Service Account"""
    if not GOOGLE_LIBS_AVAILABLE:
        print("Google libraries not available")
        return None

    try:
        BASE_DIR = Path(__file__).resolve().parent.parent
        creds_file = BASE_DIR / "oauth_credentials.json"

        if not creds_file.exists():
            print(f"❌ Service account file not found: {creds_file}")
            return None

        credentials = service_account.Credentials.from_service_account_file(
            str(creds_file),
            scopes=SCOPES
        )

        service = build('drive', 'v3', credentials=credentials)
        print("✅ Google Drive service initialized (Service Account)")
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

        final_folder_id = folder_id or os.getenv('GOOGLE_DRIVE_FOLDER_ID')

        file_metadata = {'name': filename}

        if final_folder_id:
            file_metadata['parents'] = [final_folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype='video/webm',
            resumable=True
        )

        file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink',
        supportsAllDrives=True
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

        folder = service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()

        print(f"✅ Folder created: {folder.get('id')}")
        return folder.get('id')

    except Exception as e:
        print(f"❌ Error creating folder: {e}")
        return None