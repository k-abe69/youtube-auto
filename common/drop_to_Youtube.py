import os
import json
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- Configuration ---
# Replace with your OAuth 2.0 client secrets file path
# You can get this from the Google Cloud Console (APIs & Services -> Credentials)
# Make sure you have created a project, enabled the YouTube Data API v3,
# and set up OAuth 2.0 client credentials (e.g., Desktop app).
# Download the JSON file and provide its path here.
CLIENT_SECRETS_FILE = "your_client_secret.json"

# Scope required for video upload
SCOPES = ["https://www.googleapis.com/auth/youtube-upload"]

# File to store OAuth tokens
TOKEN_FILE = "token.json"

# Directory containing the video and metadata files
OUTPUT_DIR = "output"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Authentication Function ---
def authenticate():
    """Authenticates with the YouTube Data API using OAuth 2.0."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)  # Opens a browser for authorization
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    logging.info("Authentication successful.")
    return build('youtube', 'v3', credentials=creds)

# --- Video Upload Function ---
def upload_youtube_short(youtube, script_id):
    """
    Uploads a video file to YouTube as a Short.

    Args:
        youtube: The YouTube API service object.
        script_id (str): The ID of the script (e.g., "20250529_03").
    """
    video_path = os.path.join(OUTPUT_DIR, script_id, "video.mp4")
    meta_path = os.path.join(OUTPUT_DIR, script_id, "meta.json")

    if not os.path.exists(video_path):
        logging.error(f"Video file not found: {video_path}")
        return

    if not os.path.exists(meta_path):
        logging.error(f"Metadata file not found: {meta_path}")
        return

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)
        
        title = meta_data.get("title", "Untitled Short")
        description = meta_data.get("description", "")
        hashtags = meta_data.get("hashtags", [])

        # Convert hashtags to tags, removing '#'
        tags = [tag.strip('#') for tag in hashtags if tag.startswith('#')]

        # Construct the request body
        request_body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags
            },
            "status": {
                "visibility": "public"
            }
        }

        # Initialize the media upload
        media_file = MediaFileUpload(video_path, chunkable=True)

        logging.info(f"Uploading video: {video_path}")

        # Insert the video resource
        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media_file
        )

        # Execute the upload and track progress
        while True:
            status, response = request.next_chunk()
            if status is not None:
                progress = int(status.._() * 100)
                logging.info(f"Upload progress: {progress}% complete.")
            if response is not None:
                logging.info(f"Video uploaded successfully! Video ID: {response.get('id')}")
                break

    except FileNotFoundError:
        logging.error(f"Metadata file not found: {meta_path}")
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from metadata file: {meta_path}")
    except Exception as e:
        logging.error(f"An error occurred during video upload: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    # Check if the client secrets file exists
    if not os.path.exists(CLIENT_SECRETS_FILE):
        logging.error(f"Error: Client secrets file not found at {CLIENT_SECRETS_FILE}")
        logging.error("Please download your OAuth 2.0 client secrets file from Google Cloud Console and place it here.")
    else:
        # Authenticate with the YouTube API
        youtube_service = authenticate()

        if youtube_service:
            # Specify the script ID for the video you want to upload
            script_id_to_upload = "20250529_03"  # Change this to the desired script ID

            # Upload the video
            upload_youtube_short(youtube_service, script_id_to_upload)
        else:
            logging.error("Failed to authenticate with YouTube API.")
