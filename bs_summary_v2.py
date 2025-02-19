import base64
from bs4 import BeautifulSoup
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from transformers import pipeline
from datetime import datetime
import re

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate():
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
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    return text.strip()

def get_body_from_part(part):
    """Recursively extract email body from message parts"""
    if 'parts' in part:
        for subpart in part['parts']:
            body = get_body_from_part(subpart)
            if body:
                return body
    
    if 'body' in part and 'data' in part['body']:
        if part.get('mimeType') == 'text/plain':
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        elif part.get('mimeType') == 'text/html':
            html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            soup = BeautifulSoup(html_body, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
    
    return None

def get_header_value(headers, name):
    """Extract header value with case-insensitive matching"""
    for header in headers:
        if header.get('name', '').lower() == name.lower():
            return header.get('value')
    return None

def format_timestamp(timestamp):
    """Convert Gmail timestamp to readable format"""
    dt = datetime.fromtimestamp(int(timestamp)/1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def fetch_emails():
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)
    
    results = service.users().messages().list(userId='me', maxResults=5, labelIds=['INBOX']).execute()
    messages = results.get('messages', [])

    email_data = []
    for message in messages:
        try:
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            
            headers = msg.get('payload', {}).get('headers', [])
            subject = get_header_value(headers, 'subject')
            from_address = get_header_value(headers, 'from')
            date = format_timestamp(msg['internalDate'])
            
            payload = msg.get('payload', {})
            body = get_body_from_part(payload)
            
            if not body:
                body = msg.get('snippet', 'No Content Available')
            
            body = clean_text(body)
            if not body:
                body = "No Content Available"
            
            email_data.append({
                'subject': subject or 'No Subject',
                'from': from_address,
                'date': date,
                'content': body
            })
            
        except Exception as e:
            print(f"Error processing message {message['id']}: {str(e)}")
            continue
    
    return email_data

def summarize_emails(emails):
    summarizer = pipeline('summarization', model='facebook/bart-large-cnn')
    
    print("\nEmail Summaries:")
    print("=" * 80)
    
    for email in emails:
        try:
            content = email['content']
            if len(content.strip()) < 30:
                print(f"\nDate: {email['date']}")
                print(f"From: {email['from']}")
                print(f"Subject: {email['subject']}")
                print("Summary: Content too short to summarize")
            else:
                # Truncate content if it's too long (BART model has a token limit)
                content = content[:1024]
                summary = summarizer(content, max_length=60, min_length=20, do_sample=False)[0]['summary_text']
                
                print(f"\nDate: {email['date']}")
                print(f"From: {email['from']}")
                print(f"Subject: {email['subject']}")
                print(f"Summary: {summary}")
            
            print("-" * 80)
            
        except Exception as e:
            print(f"Error summarizing email with subject '{email['subject']}': {str(e)}")
            print("-" * 80)
            continue

if __name__ == '__main__':
    try:
        print("Fetching emails from inbox...")
        emails = fetch_emails()
        if not emails:
            print("No emails found.")
        else:
            print(f"Found {len(emails)} emails. Starting summarization...")
            summarize_emails(emails)
    except Exception as e:
        print(f"An error occurred: {str(e)}")