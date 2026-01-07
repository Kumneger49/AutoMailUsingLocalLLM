"""This script should take care of getting the new emails and make it ready for the main.py"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import base64
import json
import os
import re
import asyncio
from typing import Any, List, Dict, Optional
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.header import decode_header
from pathlib import Path

# Gmail API scopes - need modify scope to mark emails as read
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

app = FastAPI()

# Store processed emails in memory (in production, use a database)
processed_emails_store: List[Dict] = []

# File to persist emails across server restarts
_emails_store_file = os.path.join(os.path.dirname(__file__), '..', '.processed_emails.json')
_processed_ids_file = os.path.join(os.path.dirname(__file__), '..', '.processed_email_ids.json')

# Global variable to store Gmail service
_gmail_service = None

# Track processed email IDs to prevent reprocessing
_processed_email_ids: set = set[Any]()


def load_emails_from_disk():
    """Load processed emails from disk."""
    global processed_emails_store, _processed_email_ids
    if os.path.exists(_emails_store_file):
        try:
            with open(_emails_store_file, 'r') as f:
                data = json.load(f)
                processed_emails_store = data.get('emails', [])
                print(f"📂 Loaded {len(processed_emails_store)} emails from disk")
        except Exception as e:
            print(f"⚠️  Error loading emails from disk: {e}")
            processed_emails_store = []
    
    # Load processed email IDs
    if os.path.exists(_processed_ids_file):
        try:
            with open(_processed_ids_file, 'r') as f:
                data = json.load(f)
                _processed_email_ids = set(data.get('email_ids', []))
                print(f"📂 Loaded {len(_processed_email_ids)} processed email IDs")
        except Exception as e:
            print(f"⚠️  Error loading processed IDs from disk: {e}")
            _processed_email_ids = set()


def save_emails_to_disk():
    """Save processed emails to disk."""
    try:
        os.makedirs(os.path.dirname(_emails_store_file), exist_ok=True)
        # Sort by date (newest first) before saving
        sorted_emails = sorted(
            processed_emails_store,
            key=lambda x: x.get('date', ''),
            reverse=True
        )
        with open(_emails_store_file, 'w') as f:
            json.dump({'emails': sorted_emails}, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving emails to disk: {e}")


def save_processed_ids_to_disk():
    """Save processed email IDs to disk."""
    try:
        os.makedirs(os.path.dirname(_processed_ids_file), exist_ok=True)
        with open(_processed_ids_file, 'w') as f:
            json.dump({'email_ids': list(_processed_email_ids)}, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving processed IDs to disk: {e}")


# Load emails on startup
load_emails_from_disk()


async def fetch_and_process_all_unread_emails():
    """Fetch all unread emails on startup and process them."""
    print("\n" + "="*60)
    print("🚀 Starting AutoMail - Fetching all unread emails...")
    print("="*60)
    
    try:
        service = get_gmail_service()
        
        # Get all unread emails from INBOX
        messages = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD'],
            maxResults=50
        ).execute()
        
        message_list = messages.get('messages', [])
        print(f"📬 Found {len(message_list)} unread email(s)")
        
        if not message_list:
            print("✅ No unread emails to process")
            return
        
        # Fetch email content
        emails = []
        for msg in message_list:
            email_data = get_email_content(msg['id'])
            if email_data and email_data.get('is_unread', True):
                emails.append(email_data)
        
        print(f"📧 Processing {len(emails)} unread email(s)...")
        
        # Filter out already processed
        new_emails = [
            e for e in emails 
            if e.get('id') not in _processed_email_ids
        ]
        
        if not new_emails:
            print("✅ All unread emails have already been processed")
            return
        
        print(f"🆕 {len(new_emails)} new email(s) to process")
        
        # Process emails
        try:
            from .main import process_emails
        except ImportError:
            from main import process_emails
        
        processed_emails = process_emails(new_emails, generate_reply=True)
        
        # Store only emails with valid content
        valid_emails = []
        for email in processed_emails:
            if email.get('summary') or email.get('draft_reply'):
                email_id = email.get('email_id')
                _processed_email_ids.add(email_id)
                processed_emails_store.append(email)
                valid_emails.append(email)
        
        # Sort by date
        processed_emails_store.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Save to disk
        save_emails_to_disk()
        save_processed_ids_to_disk()
        
        print(f"✅ Processed and stored {len(valid_emails)} email(s)")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"❌ Error fetching unread emails on startup: {e}")
        import traceback
        traceback.print_exc()


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    # Fetch all unread emails in background
    asyncio.create_task(fetch_and_process_all_unread_emails())


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main UI."""
    templates_dir = Path(__file__).parent / "templates"
    html_file = templates_dir / "index.html"
    
    if html_file.exists():
        with open(html_file, 'r') as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>AutoMail UI</h1><p>Template file not found.</p>", status_code=404)


@app.post("/")
async def root_post(request: Request):
    """Handle POST to root - redirect to proper endpoint or process if it's Pub/Sub."""
    try:
        body = await request.json()
        # Check if this looks like a Pub/Sub message
        if "message" in body:
            print("⚠️  Received Pub/Sub message at root endpoint. Redirecting to /pubsub/gmail")
            # Forward to the actual endpoint
            return await gmail_pubsub_listener(request)
        else:
            return {
                "status": "error",
                "message": "Please use /pubsub/gmail endpoint for Pub/Sub messages"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "note": "Please configure Pub/Sub to POST to /pubsub/gmail"
        }


def get_gmail_service():
    """Initialize and return Gmail API service instance."""
    global _gmail_service
    
    if _gmail_service is not None:
        return _gmail_service
    
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), '..', 'token.json')
    credentials_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
    
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
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    _gmail_service = build('gmail', 'v1', credentials=creds)
    return _gmail_service


def decode_mime_words(s):
    """Decode MIME encoded words in email headers."""
    if not s:
        return ""
    decoded_parts = decode_header(s)
    decoded_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_str += part.decode(encoding or 'utf-8', errors='ignore')
        else:
            decoded_str += part
    return decoded_str


def get_email_content(message_id: str) -> Dict:
    """Fetch and parse email content by message ID."""
    try:
        service = get_gmail_service()
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        
        # Extract headers
        headers = message['payload'].get('headers', [])
        email_data = {
            'id': message_id,
            'threadId': message.get('threadId'),
            'snippet': message.get('snippet', ''),
            'from': '',
            'to': '',
            'subject': '',
            'date': '',
            'body': ''
        }
        
        # Parse headers
        for header in headers:
            name = header['name'].lower()
            value = header['value']
            
            if name == 'from':
                email_data['from'] = decode_mime_words(value)
            elif name == 'to':
                email_data['to'] = decode_mime_words(value)
            elif name == 'subject':
                email_data['subject'] = decode_mime_words(value)
            elif name == 'date':
                email_data['date'] = value
        
        # Extract body - handle different MIME types
        payload = message['payload']
        body_text = ""
        html_body = ""
        
        def extract_body(part):
            """Recursively extract body from email parts."""
            nonlocal body_text, html_body
            mime_type = part.get('mimeType', '')
            
            # Get body data if available
            if part.get('body', {}).get('data'):
                data = part['body']['data']
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if mime_type == 'text/plain':
                        body_text += decoded + "\n"
                    elif mime_type == 'text/html':
                        html_body += decoded + "\n"
                    else:
                        # For other types, try to extract text
                        body_text += decoded + "\n"
                except Exception as e:
                    print(f"   Warning: Could not decode body part: {e}")
            
            # Recursively process parts
            if 'parts' in part:
                for subpart in part['parts']:
                    extract_body(subpart)
        
        extract_body(payload)
        
        # Prefer plain text, fall back to HTML (stripped), then snippet
        if body_text.strip():
            email_data['body'] = body_text.strip()
        elif html_body.strip():
            # Simple HTML stripping (remove tags)
            email_data['body'] = re.sub('<[^<]+?>', '', html_body).strip()
        else:
            # Fall back to snippet if no body found
            email_data['body'] = email_data.get('snippet', '')
        
        # Debug: log body extraction results
        body_len = len(email_data['body'])
        snippet_len = len(email_data.get('snippet', ''))
        
        print(f"   📄 Body extraction: body={body_len} chars, snippet={snippet_len} chars")
        
        # If body is empty or very short, use snippet (which Gmail provides)
        # Gmail snippets are usually reliable and contain the key content
        if body_len < 30 and snippet_len > 0:
            # Prefer snippet if body is too short, but keep both
            if snippet_len > body_len:
                print(f"   ⚠️  Body too short ({body_len} chars), using snippet ({snippet_len} chars) instead")
                email_data['body'] = email_data.get('snippet', '')
            else:
                # Keep body even if short, but also ensure snippet is available
                print(f"   ℹ️  Body is short ({body_len} chars), snippet available ({snippet_len} chars)")
        elif body_len == 0 and snippet_len > 0:
            # No body at all, use snippet
            print(f"   ⚠️  No body found, using snippet ({snippet_len} chars)")
            email_data['body'] = email_data.get('snippet', '')
        elif body_len < 10 and snippet_len < 10:
            # Both are very short, try to combine
            combined = (email_data.get('body', '') + ' ' + email_data.get('snippet', '')).strip()
            if len(combined) > 0:
                email_data['body'] = combined
                print(f"   ✅ Combined body and snippet: {len(combined)} chars")
            else:
                print(f"   ⚠️  Both body and snippet are very short. Body: {body_len} chars, Snippet: {snippet_len} chars")
        
        return email_data
    
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None



def get_unread_emails() -> List[Dict]:
    """Fetch all unread emails from INBOX."""
    try:
        service = get_gmail_service()
        
        # Get all unread messages from INBOX
        messages = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD'],
            maxResults=50
        ).execute()
        
        emails = []
        if 'messages' in messages:
            for msg in messages['messages']:
                email_data = get_email_content(msg['id'])
                # Only include unread emails
                if email_data and email_data.get('is_unread', True):
                    emails.append(email_data)
        
        return emails
    except Exception as e:
        print(f"   ❌ Error fetching unread emails: {e}")
        return []


def check_email_unread_status(email_id: str) -> bool:
    """Check if an email is still unread in Gmail."""
    try:
        service = get_gmail_service()
        message = service.users().messages().get(
            userId='me', 
            id=email_id, 
            format='metadata'
        ).execute()
        labels = message.get('labelIds', [])
        is_unread = 'UNREAD' in labels
        print(f"   📬 Email {email_id}: {'UNREAD' if is_unread else 'READ'}")
        return is_unread
    except HttpError as e:
        if e.resp.status == 404:
            # Email not found, assume it's been deleted/archived, treat as read
            print(f"   ⚠️  Email {email_id} not found (404), treating as read")
            return False
        print(f"   ⚠️  Error checking unread status for {email_id}: {e}")
        # On error, assume unread to be safe (don't hide emails due to API errors)
        print(f"   ⚠️  Assuming unread due to error (to avoid hiding valid emails)")
        return True
    except Exception as e:
        print(f"   ⚠️  Error checking unread status for {email_id}: {e}")
        # On error, assume unread to be safe (don't hide emails due to API errors)
        print(f"   ⚠️  Assuming unread due to error (to avoid hiding valid emails)")
        return True


@app.get("/api/emails")
async def get_emails():
    """API endpoint to get all processed emails - only returns unread emails."""
    print(f"   📊 get_emails called: {len(processed_emails_store)} emails in store")
    
    # Clean up duplicates, failed entries, and read emails
    seen_ids = set()
    cleaned_emails = []
    read_emails_removed = 0
    error_only_removed = 0
    
    for email in processed_emails_store:
        email_id = email.get('email_id')
        
        # Skip duplicates
        if email_id and email_id in seen_ids:
            print(f"   ⚠️  Duplicate email ID: {email_id}")
            continue
        if email_id:
            seen_ids.add(email_id)
        
        # Only include emails with valid content (summary or reply)
        # Skip emails that only have errors (content too short, etc.)
        has_valid_content = email.get('summary') or email.get('draft_reply')
        has_only_error = email.get('error') and not has_valid_content
        
        if has_only_error:
            # Skip emails that only have errors (like "content too short")
            print(f"   ⚠️  Skipping email with only error (no valid content): {email_id}")
            error_only_removed += 1
            continue
        
        if not has_valid_content:
            print(f"   ⚠️  Skipping email with no valid content: {email_id}")
            continue
        
        cleaned_emails.append(email)
    
    # Check unread status and remove read emails from store
    emails_to_remove = []
    for email in processed_emails_store:
        email_id = email.get('email_id')
        if email_id:
            try:
                is_unread = check_email_unread_status(email_id)
                if not is_unread:
                    print(f"   🗑️  Removing read email from store: {email_id}")
                    emails_to_remove.append(email_id)
                    read_emails_removed += 1
            except Exception as e:
                # On error, keep the email
                pass
    
    # Remove read emails from store
    if emails_to_remove:
        processed_emails_store[:] = [
            e for e in processed_emails_store
            if e.get('email_id') not in emails_to_remove
        ]
        save_emails_to_disk()
    
    # Update store with cleaned version and sort
    processed_emails_store.sort(key=lambda x: x.get('date', ''), reverse=True)
    cleaned_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    print(f"   📊 Returning {len(cleaned_emails)} emails (removed {read_emails_removed} read, {error_only_removed} error-only)")
    
    if read_emails_removed > 0 or error_only_removed > 0:
        save_emails_to_disk()
    
    return {"emails": cleaned_emails}


@app.get("/api/debug")
async def debug_info():
    """Debug endpoint to check system status."""
    return {
        "store_count": len(processed_emails_store),
        "processed_ids_count": len(_processed_email_ids),
        "store_emails": [
            {
                "email_id": e.get('email_id'),
                "subject": e.get('subject'),
                "has_summary": bool(e.get('summary')),
                "has_reply": bool(e.get('draft_reply')),
                "has_error": bool(e.get('error')),
                "error": e.get('error')
            }
            for e in processed_emails_store[:10]  # First 10
        ]
    }


@app.post("/api/fetch-emails")
async def fetch_emails_manually():
    """Manually trigger email fetching - useful for testing."""
    try:
        service = get_gmail_service()
        
        # Get current profile to get history ID
        profile = service.users().getProfile(userId='me').execute()
        current_history_id = profile.get('historyId')
        
        print(f"   🔍 Manual fetch triggered - History ID: {current_history_id}")
        
        # Get recent unread messages from INBOX
        messages = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD'],
            maxResults=10
        ).execute()
        
        print(f"   📬 Found {len(messages.get('messages', []))} unread message(s) in INBOX")
        
        emails = []
        if 'messages' in messages:
            for msg in messages['messages']:
                email_data = get_email_content(msg['id'])
                # Only include unread emails
                if email_data and email_data.get('is_unread', True):
                    emails.append(email_data)
                    print(f"   ✅ Found unread email: {email_data.get('subject', 'No Subject')}")
        
        if not emails:
            return {
                "status": "ok",
                "message": "No unread emails found",
                "emails_count": 0
            }
        
        # Process the emails
        try:
            from .main import process_emails
        except ImportError:
            from main import process_emails
        
        print(f"\n🤖 Processing {len(emails)} email(s) with Ollama...")
        
        # Filter out already processed emails
        new_emails_to_process = []
        for email in emails:
            email_id = email.get('id')
            
            if not email_id:
                continue
            
            if email_id in _processed_email_ids:
                print(f"   ⚠️  Skipping already processed email ID: {email_id}")
                continue
            
            if any(e.get('email_id') == email_id for e in processed_emails_store):
                print(f"   ⚠️  Skipping duplicate email ID in store: {email_id}")
                continue
            
            new_emails_to_process.append(email)
        
        if not new_emails_to_process:
            return {
                "status": "ok",
                "message": "All emails have already been processed",
                "emails_count": 0
            }
        
        processed_emails = process_emails(new_emails_to_process, generate_reply=True)
        
        print(f"   📊 Processing complete: {len(processed_emails)} emails processed")
        
        # Clean up: Only keep emails with valid content
        valid_emails = []
        for email in processed_emails:
            has_summary = bool(email.get('summary'))
            has_reply = bool(email.get('draft_reply'))
            
            if has_summary or has_reply:
                valid_emails.append(email)
                email_id = email.get('email_id')
                _processed_email_ids.add(email_id)
                processed_emails_store.append(email)
                print(f"   ✅ Stored valid email: {email_id}")
        
        # Sort by date
        processed_emails_store.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Save to disk
        save_emails_to_disk()
        save_processed_ids_to_disk()
        
        return {
            "status": "ok",
            "message": f"Processed {len(valid_emails)} email(s)",
            "emails_count": len(valid_emails),
            "processed_emails": valid_emails
        }
        
    except Exception as e:
        print(f"   ❌ Error in manual fetch: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }




@app.post("/api/cleanup")
async def cleanup_emails():
    """Clean up duplicate and failed email entries."""
    total_before = len(processed_emails_store)
    seen_ids = set()
    cleaned_emails = []
    duplicates_removed = 0
    failed_removed = 0
    
    for email in processed_emails_store:
        email_id = email.get('email_id')
        
        # Check for duplicates
        if email_id and email_id in seen_ids:
            duplicates_removed += 1
            continue
        if email_id:
            seen_ids.add(email_id)
        
        # Remove failed entries (no summary, no reply, no error)
        if not (email.get('summary') or email.get('draft_reply') or email.get('error')):
            failed_removed += 1
            continue
        
        cleaned_emails.append(email)
    
    processed_emails_store[:] = cleaned_emails
    save_emails_to_disk()
    
    return {
        "status": "ok",
        "total_before": total_before,
        "total_after": len(cleaned_emails),
        "duplicates_removed": duplicates_removed,
        "failed_removed": failed_removed
    }


@app.post("/pubsub/gmail")
async def gmail_pubsub_listener(request: Request):
    """Handle Gmail Pub/Sub notifications and fetch new unread emails."""
    print("📩 Gmail notification received - fetching unread emails...")
    
    try:
        # Fetch all unread emails (Pub/Sub just notifies us, we fetch all unread)
        unread_emails = get_unread_emails()
        
        if not unread_emails:
            return {"status": "ok", "message": "No unread emails"}
        
        # Filter out already processed emails
        new_emails = [
            e for e in unread_emails
            if e.get('id') not in _processed_email_ids
        ]
        
        if not new_emails:
            return {"status": "ok", "message": "All unread emails already processed"}
        
        print(f"🆕 Processing {len(new_emails)} new unread email(s)...")
        
        # Process emails
        try:
            from .main import process_emails
        except ImportError:
            from main import process_emails
        
        processed_emails = process_emails(new_emails, generate_reply=True)
        
        # Store only emails with valid content
        valid_emails = []
        for email in processed_emails:
            if email.get('summary') or email.get('draft_reply'):
                email_id = email.get('email_id')
                _processed_email_ids.add(email_id)
                processed_emails_store.append(email)
                valid_emails.append(email)
        
        # Sort by date (newest first)
        processed_emails_store.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Save to disk
        save_emails_to_disk()
        save_processed_ids_to_disk()
        
        print(f"✅ Processed {len(valid_emails)} email(s)")
        return {"status": "ok", "emails_count": len(valid_emails)}
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
