import base64
from bs4 import BeautifulSoup
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import google.generativeai as genai
from datetime import datetime
import re
import requests
from dotenv import load_dotenv
import html

# Gmail API configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

load_dotenv()  # Load variables from .env file

api_key = os.getenv("API_KEY")
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

# Gemini API configuration
GEMINI_API_KEY = api_key  # Replace with your API key
TELEGRAM_BOT_TOKEN = bot_token      # Replace with your bot token
TELEGRAM_CHAT_ID = chat_id          # Replace with your chat ID

genai.configure(api_key=GEMINI_API_KEY)


def send_telegram_message(message):
    """Send a message to a Telegram user via bot."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


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

    # Normalize spaces and newlines
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Remove email signatures and common footer elements
    text = re.sub(r'(?i)[-_]{2,}.*?(?:sent from|regards|best|thanks|signature)', '', text)
    
    # Remove quoted replies (e.g., "On [date], [name] wrote:")
    text = re.sub(r'(?i)On .*? wrote:\n.*', '', text, flags=re.DOTALL)
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    return text.strip()

def get_body_from_part(part):
    """Recursively extract email body from message parts, combining plain text and HTML"""
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

def fetch_emails(max_results=2):
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)
    
    results = service.users().messages().list(userId='me', maxResults=max_results, labelIds=['INBOX']).execute()
    messages = results.get('messages', [])

    email_data = []
    for message in messages:
        try:
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            
            headers = msg.get('payload', {}).get('headers', [])
            subject = get_header_value(headers, 'subject') or 'No Subject'
            from_address = get_header_value(headers, 'from') or 'Unknown Sender'
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
                'subject': subject,
                'from': from_address,
                'date': date,
                'content': body
            })
            
        except Exception as e:
            print(f"Error processing message {message['id']}: {str(e)}")
            continue
    
    return email_data

def summarize_with_gemini(content, subject=""):
    """Summarize content using Gemini API"""
    try:
        prompt = f"""
Please summarize the following email:
Subject: {subject}

{content}

Provide a concise summary that captures the main points, including any:
- Action items or requests
- Important dates or deadlines
- Key information
- Your summary should be 1-3 sentences.
"""

        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        return response.text.strip()
    
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return "Error generating summary with Gemini API"

def summarize_emails(emails):
    print("\nEmail Summaries:")
    print("=" * 80)
    
    for email in emails:
        try:
            content = email['content']
            subject = email['subject']
            
            if len(content.strip()) < 30:
                # print(f"\nDate: {email['date']}")
                # print(f"From: {email['from']}")
                # print(f"Subject: {subject}")
                # print("Summary: Content too short to summarize")

                short_msg = (
                    f"<b>Date:</b> {html.escape(email['date'])}\n"
                    f"<b>From:</b> {html.escape(email['from'])}\n"
                    f"<b>Subject:</b> {html.escape(subject)}\n"
                    f"<b>Summary:</b> Content too short to summarize"
                )
                send_telegram_message(short_msg)
                print(short_msg)

            else:
                # Use Gemini to summarize
                summary = summarize_with_gemini(content, subject)
                
                # print(f"\nDate: {email['date']}")
                # print(f"From: {email['from']}")
                # print(f"Subject: {subject}")
                # print(f"Summary: {summary}")

                summary_msg = (
                    f"<b>Date:</b> {html.escape(email['date'])}\n"
                    f"<b>From:</b> {html.escape(email['from'])}\n"
                    f"<b>Subject:</b> {html.escape(subject)}\n"
                    f"<b>Summary:</b> {html.escape(summary)}"
                )
                send_telegram_message(summary_msg)
                print(summary_msg)
                   
            print("-" * 80)
            
        except Exception as e:
            print(f"Error summarizing email: {str(e)}")
            print("-" * 80)
            continue

if __name__ == '__main__':
    try:
        # list_available_models()
        print("Fetching emails from inbox...")
        emails = fetch_emails(max_results=3)
        if not emails:
            print("No emails found.")
        else:
            print(f"Found {len(emails)} emails. Starting summarization...")
            summarize_emails(emails)

    except Exception as e:
        print(f"An error occurred: {str(e)}")