"""This script will read the current email the user just received and make a summary for the user"""

from ollama import generate
from typing import Dict, List, Optional
import time


def summarize_email(email_data: Dict) -> Dict:
    """
    Generate a summary of an email using Ollama.
    
    Args:
        email_data: Dictionary containing email information (from, subject, body, etc.)
    
    Returns:
        Dictionary with summary and processing time
    """
    from_email = email_data.get('from', 'Unknown')
    subject = email_data.get('subject', 'No Subject')
    body = email_data.get('body', '')
    snippet = email_data.get('snippet', '')
    
    # Use body if available, otherwise use snippet
    # Gmail snippets are often more reliable for short emails
    # Prefer body if it has substantial content (>30 chars), otherwise use snippet
    if body and len(body.strip()) > 30:
        email_content = body
        print(f"   📝 Using email body ({len(body)} chars)")
    elif snippet and len(snippet.strip()) > 0:
        email_content = snippet
        print(f"   📝 Using email snippet ({len(snippet)} chars) - body was too short or empty")
    elif body and len(body.strip()) > 0:
        # Use body even if short (at least it's something)
        email_content = body
        print(f"   📝 Using short email body ({len(body)} chars)")
    else:
        # Last resort: try to combine or use whatever we have
        email_content = (body + " " + snippet).strip() if (body and snippet) else (body or snippet or "")
        
        if len(email_content.strip()) < 3:
            print(f"   ⚠️  Warning: Email content is too short. Body: {len(body)} chars, Snippet: {len(snippet)} chars")
            return {
                "summary": "Unable to generate summary: email content is too short or empty.",
                "processing_time": 0,
                "status": "error",
                "error": "Email content too short"
            }
        else:
            print(f"   📝 Using combined/fallback content ({len(email_content)} chars)")
    
    prompt = f"""Summarize this email in 2-3 sentences. Focus on the main request, action items, or important information.

From: {from_email}
Subject: {subject}
Content: {email_content}

Summary:"""
    
    try:
        start_time = time.time()
        response = generate(model="llama3.2:latest", prompt=prompt)
        end_time = time.time()
        
        # Ollama returns a dict, access 'response' key
        summary = response.get('response', '').strip()
        processing_time = end_time - start_time
        
        return {
            "summary": summary,
            "processing_time": round(processing_time, 2),
            "status": "success"
        }
    except Exception as e:
        return {
            "summary": None,
            "processing_time": 0,
            "status": "error",
            "error": str(e)
        }


def generate_draft_reply(email_data: Dict, tone: str = "professional") -> Dict:
    """
    Generate a draft reply to an email using Ollama.
    
    Args:
        email_data: Dictionary containing email information
        tone: Tone of the reply (professional, casual, friendly)
    
    Returns:
        Dictionary with draft reply and processing time
    """
    from_email = email_data.get('from', 'Unknown')
    subject = email_data.get('subject', 'No Subject')
    body = email_data.get('body', '')
    snippet = email_data.get('snippet', '')
    
    # Use body if available, otherwise use snippet
    # Gmail snippets are often more reliable for short emails
    # Prefer body if it has substantial content (>30 chars), otherwise use snippet
    if body and len(body.strip()) > 30:
        email_content = body
        print(f"   📝 Using email body ({len(body)} chars)")
    elif snippet and len(snippet.strip()) > 0:
        email_content = snippet
        print(f"   📝 Using email snippet ({len(snippet)} chars) - body was too short or empty")
    elif body and len(body.strip()) > 0:
        # Use body even if short (at least it's something)
        email_content = body
        print(f"   📝 Using short email body ({len(body)} chars)")
    else:
        # Last resort: try to combine or use whatever we have
        email_content = (body + " " + snippet).strip() if (body and snippet) else (body or snippet or "")
        
        if len(email_content.strip()) < 3:
            print(f"   ⚠️  Warning: Email content is too short. Body: {len(body)} chars, Snippet: {len(snippet)} chars")
            return {
                "draft_reply": "Unable to generate reply: email content is too short or empty.",
                "processing_time": 0,
                "status": "error",
                "error": "Email content too short"
            }
        else:
            print(f"   📝 Using combined/fallback content ({len(email_content)} chars)")
    
    prompt = f"""Write a concise, {tone} reply to this email. Keep it brief and to the point.

Original Email:
From: {from_email}
Subject: {subject}
Content: {email_content}

Draft Reply:"""
    
    try:
        start_time = time.time()
        response = generate(model="llama3.2:latest", prompt=prompt)
        end_time = time.time()
        
        # Ollama returns a dict, access 'response' key
        draft_reply = response.get('response', '').strip()
        processing_time = end_time - start_time
        
        return {
            "draft_reply": draft_reply,
            "processing_time": round(processing_time, 2),
            "status": "success"
        }
    except Exception as e:
        return {
            "draft_reply": None,
            "processing_time": 0,
            "status": "error",
            "error": str(e)
        }


def process_email(email_data: Dict, generate_reply: bool = True) -> Dict:
    """
    Process an email: generate summary and optionally a draft reply.
    
    Args:
        email_data: Dictionary containing email information
        generate_reply: Whether to generate a draft reply (default: True)
    
    Returns:
        Dictionary with processed email data including summary and reply
    """
    print(f"\n📧 Processing email: {email_data.get('subject', 'No Subject')}")
    print(f"   From: {email_data.get('from', 'Unknown')}")
    
    # Generate summary
    print("   Generating summary...")
    summary_result = summarize_email(email_data)
    
    result = {
        "email_id": email_data.get('id'),
        "from": email_data.get('from'),
        "subject": email_data.get('subject'),
        "date": email_data.get('date'),
        "body": email_data.get('body', ''),  # Include original body as fallback
        "snippet": email_data.get('snippet', ''),  # Include snippet as fallback
        "summary": summary_result.get('summary'),
        "summary_time": summary_result.get('processing_time'),
    }
    
    if summary_result.get('status') == 'error':
        result['error'] = summary_result.get('error')
        print(f"   ❌ Error generating summary: {summary_result.get('error')}")
    else:
        summary_text = summary_result.get('summary', '')
        print(f"   ✅ Summary generated ({summary_result.get('processing_time')}s)")
        print(f"   Summary:\n   {summary_text}")
    
    # Generate draft reply if requested
    if generate_reply:
        print("   Generating draft reply...")
        reply_result = generate_draft_reply(email_data)
        
        result['draft_reply'] = reply_result.get('draft_reply')
        result['reply_time'] = reply_result.get('processing_time')
        
        if reply_result.get('status') == 'error':
            result['reply_error'] = reply_result.get('error')
            print(f"   ❌ Error generating reply: {reply_result.get('error')}")
        else:
            reply_text = reply_result.get('draft_reply', '')
            print(f"   ✅ Draft reply generated ({reply_result.get('processing_time')}s)")
            print(f"   Draft Reply:\n   {reply_text}")
    
    return result


def process_emails(emails: List[Dict], generate_reply: bool = True) -> List[Dict]:
    """
    Process multiple emails.
    
    Args:
        emails: List of email dictionaries
        generate_reply: Whether to generate draft replies (default: True)
    
    Returns:
        List of processed email results
    """
    results = []
    
    for email_data in emails:
        try:
            processed = process_email(email_data, generate_reply)
            results.append(processed)
        except Exception as e:
            print(f"❌ Error processing email {email_data.get('id', 'unknown')}: {e}")
            results.append({
                "email_id": email_data.get('id'),
                "error": str(e)
            })
    
    return results
