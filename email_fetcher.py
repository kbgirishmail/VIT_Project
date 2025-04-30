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
import time # Import time for timestamp calculations

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate():
    """Authenticate to Gmail API"""
    creds = None
    # Check if token.json exists
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception as e:
            print(f"Warning: Could not load token.json ({e}). Will try to re-authenticate.")
            creds = None # Ensure creds is None if loading fails

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired credentials...")
                creds.refresh(Request())
                print("Credentials refreshed.")
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                print("Attempting full re-authentication...")
                creds = None # Force re-auth
        # Only run flow if creds are still None (initial auth or failed refresh)
        if not creds:
             try:
                print("No valid credentials found, starting authentication flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                print("Authentication successful.")
             except FileNotFoundError:
                  print("Error: credentials.json not found. Please download it from Google Cloud Console.")
                  return None # Cannot authenticate without credentials file
             except Exception as e:
                  print(f"Error during authentication flow: {e}")
                  return None # Authentication failed


        # Save the credentials for the next run
        if creds:
             try:
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
                print("Credentials saved to token.json.")
             except Exception as e:
                  print(f"Error saving token.json: {e}")

    # Check if creds object exists before returning
    if not creds:
         print("Authentication ultimately failed.")
    return creds

def clean_text(text):
    """Clean and normalize text content"""
    if not text:
        return ""

    # Remove multiple newlines and spaces
    text = re.sub(r'\s*\n\s*', '\n', text) # Consolidate newlines and strip surrounding whitespace
    text = re.sub(r'[ \t]+', ' ', text) # Consolidate spaces/tabs

    # Remove email signatures and common footer elements more robustly
    # Look for patterns like "--" or common phrases, remove everything after
    text_lines = text.split('\n')
    cleaned_lines = []
    signature_found = False
    signature_patterns = [
        re.compile(r'^\s*--\s*$'), # Common signature separator
        re.compile(r'^(?:best|regards|sincerely|thanks|cheers|yours|cordially)\s*,?\s*$', re.IGNORECASE),
        re.compile(r'^(?:sent from|get outlook for|transmitted).*$', re.IGNORECASE)
    ]
    common_phrases = ['sent from my iphone', 'sent from android', 'regards', 'best regards', 'sincerely']

    for line in text_lines:
        # Check for signature patterns
        if any(pattern.match(line) for pattern in signature_patterns):
            signature_found = True
        # Check if line predominantly contains signature-like info (often after a gap)
        if len(cleaned_lines) > 1 and not cleaned_lines[-1].strip() and any(phrase in line.lower() for phrase in common_phrases):
             signature_found = True

        if signature_found:
            continue # Skip this line and all subsequent lines

        cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)

    # Remove quoted replies (try a few common patterns)
    # Pattern 1: "On [Date], [Name] <email> wrote:"
    text = re.sub(r'(?im)^\s*On\s.+?\s+wrote:\s*$.*?(?=(?:^\s*On\s.+?\s+wrote:\s*$|\Z))', '', text, flags=re.DOTALL)
    # Pattern 2: ">" quoted lines at the beginning
    text = re.sub(r'(?m)^\s*>.*$\n?', '', text)
    # Pattern 3: Lines starting with "From:", "Sent:", "To:", "Subject:" often indicate forwarded headers
    text = re.sub(r'(?im)^\s*(?:From|Sent|To|Subject)\s*:.*$\n?', '', text)


    # Remove URLs (optional, uncomment if desired)
    # text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', 'https://www.merriam-webster.com/dictionary/removed', text)

    return text.strip()


def get_body_from_part(part):
    """
    Recursively extract email body from message parts.
    Prioritizes text/plain, then text/html.
    Returns tuple (text_body, html_body_raw)
    """
    text_body = ""
    html_body_raw = ""

    mime_type = part.get('mimeType', '')

    if mime_type == 'text/plain' and 'data' in part.get('body', {}):
        try:
            text_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Warning: Could not decode text/plain part: {e}")
            text_body = "[Undecodable Text Part]"

    elif mime_type == 'text/html' and 'data' in part.get('body', {}):
        try:
            html_body_raw = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
        except Exception as e:
            print(f"Warning: Could not decode text/html part: {e}")
            html_body_raw = ""

    # Recurse into multipart/* parts
    elif mime_type.startswith('multipart/'):
        if 'parts' in part:
            child_text = ""
            child_html = ""
            # Prioritize multipart/alternative for finding best version
            if mime_type == 'multipart/alternative':
                # Look for text/plain first, then text/html
                plain_part = next((p for p in part['parts'] if p.get('mimeType') == 'text/plain'), None)
                if plain_part:
                    t, _ = get_body_from_part(plain_part)
                    child_text += t + "\n"
                else: # If no plain, take the html
                    html_part = next((p for p in part['parts'] if p.get('mimeType') == 'text/html'), None)
                    if html_part:
                         _, h = get_body_from_part(html_part)
                         child_html += h + "\n"
            else: # For other multipart types, just concatenate
                for subpart in part['parts']:
                    t, h = get_body_from_part(subpart)
                    child_text += t + "\n"
                    child_html += h + "\n"

            text_body = child_text.strip()
            html_body_raw = child_html.strip()

    return text_body.strip(), html_body_raw.strip()


def extract_text_from_html(html_content):
    """Extracts readable text from HTML content using BeautifulSoup."""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Get text, use newline as separator, strip leading/trailing whitespace
        text = soup.get_text(separator='\n', strip=True)

        # Optional: Further cleanups specific to HTML-extracted text
        text = re.sub(r'\n{3,}', '\n\n', text) # Reduce multiple blank lines

        return text
    except Exception as e:
        print(f"Error parsing HTML with BeautifulSoup: {e}")
        return "[HTML Parsing Error]"


def get_header_value(headers, name):
    """Extract header value with case-insensitive matching"""
    if not headers: return None
    for header in headers:
        if header.get('name', '').lower() == name.lower():
            return header.get('value')
    return None

def format_timestamp(timestamp_ms):
    """Convert Gmail timestamp (milliseconds string) to readable format"""
    if not timestamp_ms:
        return "Unknown Date"
    try:
        # Convert milliseconds string to integer, then to seconds float
        timestamp_sec = int(timestamp_ms) / 1000.0
        dt = datetime.fromtimestamp(timestamp_sec)
        # Consider using local timezone or UTC display
        return dt.strftime("%Y-%m-%d %H:%M:%S") # Local time zone display
        # return dt.strftime("%Y-%m-%d %H:%M:%S %Z") # Include timezone
    except (ValueError, TypeError, OverflowError) as e:
        print(f"Warning: Could not format timestamp '{timestamp_ms}': {e}")
        return "Invalid Date"

# --- MODIFIED FUNCTION ---
def fetch_emails_since(days=1, query=None, max_results=50): # Added 'query=None'
    """
    Fetch emails within a given timeframe or using a specific query.
    Uses 'query' if provided, otherwise calculates based on 'days'.
    """
    creds = authenticate()
    if not creds: # Handle auth failure
         print("Authentication failed. Cannot fetch emails.")
         return []
    try:
        service = build('gmail', 'v1', credentials=creds)
    except Exception as e:
         print(f"Error building Gmail service: {e}")
         return []


    # --- Determine the search query ---
    search_query = query # Start with the provided query
    if not search_query: # If no query was given...
        if days is not None: # ...and days is specified...
             try:
                 days_float = float(days)
                 if days_float < 0:
                      print("Warning: 'days' cannot be negative. Fetching without time filter.")
                      search_query = "in:inbox" # Default to just inbox
                 else:
                      time_cutoff = datetime.now() - timedelta(days=days_float)
                      query_timestamp = int(time_cutoff.timestamp()) # Seconds since epoch
                      search_query = f"in:inbox after:{query_timestamp}" # Include inbox filter
                      print(f"Fetching emails using calculated 'days={days_float}', query: '{search_query}'")

             except (ValueError, TypeError):
                 print(f"Warning: Invalid 'days' value '{days}'. Fetching without time filter.")
                 search_query = "in:inbox" # Default to just inbox if days is invalid
        else:
             # No query and no valid days - fetch recent inbox items (Gmail default)
             print("Warning: No query or valid 'days' provided. Fetching recent inbox emails.")
             search_query = "in:inbox"
    else:
         # If query is provided, maybe ensure it includes inbox? Optional.
         if "in:inbox" not in search_query.lower() and "label:" not in search_query.lower():
              print(f"Enhancing provided query with 'in:inbox': '{search_query}'")
              search_query = f"in:inbox {search_query}" # Prepend inbox filter if not present
         else:
              print(f"Fetching emails using provided query: '{search_query}'")
    # ----------------------------------

    email_data = []
    try:
        # List messages matching the query
        results = service.users().messages().list(
            userId='me',
            q=search_query,
            maxResults=min(max_results, 500), # API limit is higher, but be reasonable
            labelIds=['INBOX'] # Explicitly only INBOX, overrides label: in query if needed
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            # print(f"No emails found matching query '{search_query}'.") # Less verbose output
            return [] # Return empty list if no messages match

        print(f"Found {len(messages)} message IDs matching query. Fetching details (max {max_results})...")

        # Fetch details for each message (up to max_results)
        processed_count = 0
        for message_summary in messages:
            if processed_count >= max_results:
                 print(f"Reached max_results limit ({max_results}). Stopping fetch.")
                 break
            message_id = message_summary.get('id')
            if not message_id: continue # Skip if no ID somehow

            try:
                # Request 'full' format to get headers, body parts, etc.
                msg = service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()

                payload = msg.get('payload', {})
                headers = payload.get('headers', [])

                # Extract key information
                subject = get_header_value(headers, 'subject') or 'No Subject'
                from_address = get_header_value(headers, 'from') or 'Unknown Sender'
                to_address = get_header_value(headers, 'to') or ''
                internal_date_ms = msg.get('internalDate')
                date_str = format_timestamp(internal_date_ms) if internal_date_ms else "Unknown Date"

                # Extract body content
                text_body, html_body_raw = get_body_from_part(payload)

                # Prefer plain text, otherwise parse HTML
                final_body = text_body
                if not final_body and html_body_raw:
                    # print(f"Parsing HTML body for message {message_id}...") # Debugging line
                    final_body = extract_text_from_html(html_body_raw)

                # Fallback to snippet if body extraction failed
                if not final_body:
                    final_body = msg.get('snippet', '[No Content Available]')

                # Clean the final extracted/parsed body
                cleaned_body = clean_text(final_body)

                # If cleaning results in empty, use original snippet (might be better than nothing)
                if not cleaned_body and msg.get('snippet'):
                    cleaned_body = f"[Snippet]: {msg.get('snippet')}"
                elif not cleaned_body:
                    cleaned_body = "[No Meaningful Content Found]"


                email_data.append({
                    'id': message_id,
                    'threadId': msg.get('threadId'),
                    'subject': subject,
                    'from': from_address,
                    'to': to_address,
                    'date': date_str, # Formatted date string
                    'internalDate': internal_date_ms, # Original timestamp (ms string)
                    'content': cleaned_body, # The primary text content for processing
                    'snippet': msg.get('snippet', '') # Original snippet
                })
                processed_count += 1

            except Exception as e:
                print(f"Error processing message details for ID {message_id}: {e}")
                # Optionally log more details about the error or the message structure
                continue # Skip to next message on error

        print(f"Successfully fetched and processed details for {len(email_data)} emails.")


    except Exception as e:
        # Catch errors during the list or subsequent get calls
        print(f"An error occurred during email fetching: {e}")
        # Potentially log the full traceback here for debugging
        # import traceback
        # traceback.print_exc()

    return email_data # Return whatever was successfully processed