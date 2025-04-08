# email_fetcher.py
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import base64
from bs4 import BeautifulSoup
import re

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate():
    """Authenticate to Gmail API"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def clean_text(text):
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove multiple newlines and spaces
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Remove email signatures and common footer elements
    text = re.sub(r'(?i)[-_]{2,}.*?(?:sent from|regards|best|thanks|signature)', '', text)
    
    # Remove quoted replies
    text = re.sub(r'(?i)On .*? wrote:\n.*', '', text, flags=re.DOTALL)
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    return text.strip()

def get_body_from_part(part):
    """Recursively extract email body from message parts"""
    if 'parts' in part:
        text_body, html_body = "", ""
        for subpart in part['parts']:
            t, h = get_body_from_part(subpart)
            text_body += t
            html_body += h
        return text_body.strip(), html_body.strip()

    text_body, html_body = "", ""

    if 'body' in part and 'data' in part['body']:
        data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
        if part.get('mimeType') == 'text/plain':
            text_body = data
        elif part.get('mimeType') == 'text/html':
            soup = BeautifulSoup(data, 'html.parser')
            html_body = soup.get_text(separator='\n', strip=True)

    return text_body.strip(), html_body.strip()

def get_header_value(headers, name):
    """Extract header value with case-insensitive matching"""
    for header in headers:
        if header.get('name', '').lower() == name.lower():
            return header.get('value')
    return None

def format_timestamp(timestamp):
    """Convert Gmail timestamp to readable format"""
    try:
        dt = datetime.fromtimestamp(int(timestamp) / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "Unknown Date"

def fetch_emails_since(days=1, max_results=50):
    """Fetch emails from the past X days"""
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)
    
    # Calculate time period
    time_period = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    query = f"after:{int(time_period/1000)}"
    
    try:
        results = service.users().messages().list(
            userId='me', 
            q=query, 
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            print(f"No emails found in the past {days} days.")
            return []
        
        email_data = []
        for message in messages:
            try:
                msg = service.users().messages().get(
                    userId='me', 
                    id=message['id'], 
                    format='full'
                ).execute()
                
                headers = msg.get('payload', {}).get('headers', [])
                subject = get_header_value(headers, 'subject') or 'No Subject'
                from_address = get_header_value(headers, 'from') or 'Unknown Sender'
                to_address = get_header_value(headers, 'to') or ''
                date = format_timestamp(msg.get('internalDate', 0))
                
                payload = msg.get('payload', {})
                text_body, html_body = get_body_from_part(payload)
                
                # Prefer text/plain, but fallback to cleaned HTML if missing
                body = text_body if text_body else html_body
                if not body:
                    body = msg.get('snippet', 'No Content Available')
                
                # Clean the extracted text
                body = clean_text(body)
                if not body:
                    body = "No Content Available"
                
                email_data.append({
                    'id': message['id'],
                    'subject': subject,
                    'from': from_address,
                    'to': to_address,
                    'date': date,
                    'content': body
                })
                
            except Exception as e:
                print(f"Error processing message {message['id']}: {str(e)}")
                continue
        
        return email_data
        
    except Exception as e:
        print(f"Error fetching emails: {str(e)}")
        return []