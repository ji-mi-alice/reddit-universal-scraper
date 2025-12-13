"""
Cloud Upload Module - S3 and Google Drive integration
"""
import os
import json
from pathlib import Path
from datetime import datetime

# Try importing boto3 for S3
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# Try importing Google Drive API
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False


class S3Uploader:
    """Upload scraped data to AWS S3."""
    
    def __init__(self, bucket_name, aws_access_key=None, aws_secret_key=None, region='us-east-1'):
        """
        Initialize S3 uploader.
        
        Args:
            bucket_name: S3 bucket name
            aws_access_key: Optional, uses env/config if not provided
            aws_secret_key: Optional, uses env/config if not provided
            region: AWS region
        """
        if not HAS_BOTO3:
            raise ImportError("boto3 not installed. Run: pip install boto3")
        
        self.bucket_name = bucket_name
        self.region = region
        
        # Use provided credentials or fall back to env vars
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key or os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=aws_secret_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region
        )
    
    def upload_file(self, local_path, s3_key=None):
        """
        Upload a single file to S3.
        
        Args:
            local_path: Local file path
            s3_key: S3 object key (default: same as filename)
        
        Returns:
            S3 URL or None on failure
        """
        local_path = Path(local_path)
        
        if not local_path.exists():
            print(f"❌ File not found: {local_path}")
            return None
        
        s3_key = s3_key or local_path.name
        
        try:
            self.s3.upload_file(str(local_path), self.bucket_name, s3_key)
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            print(f"✅ Uploaded: {s3_key}")
            return url
        except ClientError as e:
            print(f"❌ S3 upload failed: {e}")
            return None
    
    def upload_directory(self, local_dir, s3_prefix=""):
        """
        Upload entire directory to S3.
        
        Args:
            local_dir: Local directory path
            s3_prefix: Prefix for S3 keys
        
        Returns:
            Dictionary of uploaded files
        """
        local_dir = Path(local_dir)
        
        if not local_dir.exists():
            print(f"❌ Directory not found: {local_dir}")
            return {}
        
        uploaded = {}
        
        for file_path in local_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                s3_key = f"{s3_prefix}/{relative_path}" if s3_prefix else str(relative_path)
                s3_key = s3_key.replace('\\', '/')  # Windows path fix
                
                url = self.upload_file(file_path, s3_key)
                if url:
                    uploaded[str(relative_path)] = url
        
        print(f"\n📤 Uploaded {len(uploaded)} files to S3")
        return uploaded
    
    def upload_subreddit_data(self, subreddit, prefix="u"):
        """
        Upload all data for a subreddit.
        
        Args:
            subreddit: Subreddit name
            prefix: "r" for subreddit, "u" for user
        
        Returns:
            Upload results
        """
        data_dir = Path(f"data/{prefix}_{subreddit}")
        
        if not data_dir.exists():
            print(f"❌ Data not found for {prefix}/{subreddit}")
            return {}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_prefix = f"reddit/{prefix}_{subreddit}/{timestamp}"
        
        return self.upload_directory(data_dir, s3_prefix)
    
    def list_uploads(self, prefix="reddit/"):
        """List all uploaded data in S3."""
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            objects = response.get('Contents', [])
            
            print(f"\n📁 S3 Contents ({self.bucket_name}/{prefix}):")
            for obj in objects[:50]:  # Limit to 50
                size_kb = obj['Size'] / 1024
                print(f"   {obj['Key']} ({size_kb:.1f} KB)")
            
            if len(objects) > 50:
                print(f"   ... and {len(objects) - 50} more")
            
            return objects
        except ClientError as e:
            print(f"❌ S3 list failed: {e}")
            return []


class GDriveUploader:
    """Upload scraped data to Google Drive."""
    
    def __init__(self, credentials_file='credentials.json', token_file='token.json'):
        """
        Initialize Google Drive uploader.
        
        Args:
            credentials_file: Path to OAuth credentials JSON
            token_file: Path to token JSON
        """
        if not HAS_GDRIVE:
            raise ImportError("Google API client not installed. Run: pip install google-api-python-client google-auth-oauthlib")
        
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                from google_auth_oauthlib.flow import InstalledAppFlow
                SCOPES = ['https://www.googleapis.com/auth/drive.file']
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('drive', 'v3', credentials=creds)
        print("✅ Google Drive authenticated")
    
    def create_folder(self, name, parent_id=None):
        """Create a folder in Google Drive."""
        metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            metadata['parents'] = [parent_id]
        
        folder = self.service.files().create(body=metadata, fields='id').execute()
        return folder.get('id')
    
    def upload_file(self, local_path, folder_id=None):
        """Upload a file to Google Drive."""
        local_path = Path(local_path)
        
        if not local_path.exists():
            print(f"❌ File not found: {local_path}")
            return None
        
        metadata = {'name': local_path.name}
        if folder_id:
            metadata['parents'] = [folder_id]
        
        media = MediaFileUpload(str(local_path), resumable=True)
        
        try:
            file = self.service.files().create(
                body=metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            print(f"✅ Uploaded: {local_path.name}")
            return file.get('webViewLink')
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return None
    
    def upload_subreddit_data(self, subreddit, prefix="r"):
        """Upload all data for a subreddit."""
        data_dir = Path(f"data/{prefix}_{subreddit}")
        
        if not data_dir.exists():
            print(f"❌ Data not found for {prefix}/{subreddit}")
            return {}
        
        # Create folder structure
        root_folder = self.create_folder(f"reddit_{prefix}_{subreddit}_{datetime.now().strftime('%Y%m%d')}")
        
        uploaded = {}
        
        for file_path in data_dir.rglob('*'):
            if file_path.is_file():
                url = self.upload_file(file_path, root_folder)
                if url:
                    uploaded[str(file_path.name)] = url
        
        print(f"\n📤 Uploaded {len(uploaded)} files to Google Drive")
        return uploaded


def upload_to_s3(subreddit, bucket_name, prefix="r"):
    """
    Convenience function to upload subreddit data to S3.
    
    Args:
        subreddit: Subreddit name
        bucket_name: S3 bucket name
        prefix: "r" or "u"
    
    Returns:
        Upload results
    """
    uploader = S3Uploader(bucket_name)
    return uploader.upload_subreddit_data(subreddit, prefix)


def upload_to_gdrive(subreddit, prefix="r"):
    """
    Convenience function to upload subreddit data to Google Drive.
    
    Args:
        subreddit: Subreddit name
        prefix: "r" or "u"
    
    Returns:
        Upload results
    """
    uploader = GDriveUploader()
    return uploader.upload_subreddit_data(subreddit, prefix)


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cloud Upload")
    parser.add_argument("subreddit", help="Subreddit to upload")
    parser.add_argument("--s3-bucket", help="S3 bucket name")
    parser.add_argument("--gdrive", action="store_true", help="Upload to Google Drive")
    parser.add_argument("--user", action="store_true", help="Is a user profile")
    
    args = parser.parse_args()
    prefix = "u" if args.user else "r"
    
    if args.s3_bucket:
        upload_to_s3(args.subreddit, args.s3_bucket, prefix)
    elif args.gdrive:
        upload_to_gdrive(args.subreddit, prefix)
    else:
        print("Please specify --s3-bucket or --gdrive")
