"""
Script to set up Gmail watch for push notifications to Pub/Sub topic.
Run this script once to configure Gmail to send notifications to your Pub/Sub topic.
"""

import os
import json
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes - need modify scope for watch
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/pubsub'
]

def get_gmail_service():
    """Initialize and return Gmail API service instance."""
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), 'token.json')
    credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
    
    # Load existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"credentials.json not found at {credentials_path}. "
                    "Please download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


def setup_gmail_watch(topic_name: str):
    """
    Set up Gmail watch to send push notifications to Pub/Sub topic.
    
    Args:
        topic_name: Full Pub/Sub topic name (e.g., 'projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME')
    
    Note: Gmail watch expires after 7 days and needs to be renewed.
    """
    try:
        service = get_gmail_service()
        
        # Get current profile to verify authentication
        profile = service.users().getProfile(userId='me').execute()
        print(f"✅ Authenticated as: {profile.get('emailAddress')}")
        
        # Set up watch
        watch_request = {
            'topicName': topic_name,
            'labelIds': ['INBOX']  # Watch for emails in INBOX
        }
        
        print(f"\n📡 Setting up Gmail watch...")
        print(f"   Topic: {topic_name}")
        print(f"   Watching: INBOX")
        
        watch_response = service.users().watch(userId='me', body=watch_request).execute()
        
        print(f"\n✅ Gmail watch set up successfully!")
        print(f"   History ID: {watch_response.get('historyId')}")
        print(f"   Expiration: {watch_response.get('expiration')}")
        print(f"\n⚠️  Note: Gmail watch expires after 7 days.")
        print(f"   You'll need to run this script again to renew it.")
        
        return watch_response
    
    except HttpError as error:
        print(f"❌ An error occurred: {error}")
        if error.resp.status == 403:
            print("\n💡 Common issues:")
            print("   1. Make sure Pub/Sub API is enabled")
            print("   2. Grant 'pubsub.topics.publish' permission to gmail-api-push@system.gserviceaccount.com")
            print("   3. Verify your topic name is correct (full path)")
        raise


def grant_pubsub_permission(project_id: str, topic_name: str):
    """
    Instructions for granting Pub/Sub permissions to Gmail.
    This needs to be done in Google Cloud Console.
    """
    print("\n" + "="*60)
    print("IMPORTANT: Grant Pub/Sub Permission to Gmail")
    print("="*60)
    print("\nYou need to grant Gmail permission to publish to your Pub/Sub topic:")
    print("\n1. Go to Google Cloud Console > Pub/Sub > Topics")
    print(f"2. Click on your topic: {topic_name}")
    print("3. Click 'PERMISSIONS' tab")
    print("4. Click 'GRANT ACCESS'")
    print("5. Add this principal: gmail-api-push@system.gserviceaccount.com")
    print("6. Select role: 'Pub/Sub Publisher'")
    print("7. Click 'SAVE'")
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    print("="*60)
    print("Gmail Watch Setup for AutoMail")
    print("="*60)
    
    # Get topic name from user
    print("\nEnter your Pub/Sub topic name.")
    print("Format: projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME")
    print("Example: projects/my-project-123/topics/gmail-notifications")
    
    topic_name = input("\nTopic name: ").strip()
    
    if not topic_name:
        print("❌ Topic name cannot be empty!")
        exit(1)
    
    # Extract project ID for permission instructions
    if topic_name.startswith('projects/'):
        parts = topic_name.split('/')
        if len(parts) >= 2:
            project_id = parts[1]
        else:
            project_id = "YOUR_PROJECT_ID"
    else:
        project_id = "YOUR_PROJECT_ID"
        print("⚠️  Warning: Topic name should start with 'projects/'. Using full path anyway...")
    
    # Show permission instructions
    grant_pubsub_permission(project_id, topic_name)
    
    input("Press Enter after you've granted the Pub/Sub permission...")
    
    # Set up watch
    try:
        setup_gmail_watch(topic_name)
        print("\n🎉 Setup complete! Gmail will now send notifications to your Pub/Sub topic.")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")

