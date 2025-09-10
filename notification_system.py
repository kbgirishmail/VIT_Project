# notification_system.py
import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# requests is not used in the provided code, can be removed if not needed elsewhere
# from datetime import datetime # Not used directly here, can be removed
from dotenv import load_dotenv
from datetime import datetime 

# Attempt to import optional dependencies
TWILIO_AVAILABLE = False
FCM_AVAILABLE = False

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    pass # Keep TWILIO_AVAILABLE as False

try:
    from pyfcm import FCMNotification
    FCM_AVAILABLE = True
except ImportError:
    pass # Keep FCM_AVAILABLE as False

# Load environment variables
load_dotenv()

def load_config():
    """Load user configuration safely."""
    config_path = 'config.json' # Define path explicitly
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                # Handle empty file case
                content = f.read()
                if not content:
                     print(f"Warning: Config file '{config_path}' is empty.")
                     return {}
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from '{config_path}'. Check its format.")
            return {} # Return empty dict on decode error
        except Exception as e:
            print(f"Error loading config file '{config_path}': {e}")
            return {} # Return empty dict on other errors
    else:
        # It's better for the main script to handle missing config/setup
        print(f"Warning: Config file '{config_path}' not found.")
        return {}

# Note: This function sends alerts for *individual* critical emails
# It's called by send_notifications_for_batch based on rules
def send_email_notification(email_data, config):
    """Send email notification styled as an alert for a single important email."""
    # Get SMTP config details safely
    smtp_server = config.get('smtp_server')
    smtp_port = config.get('smtp_port')
    smtp_username = config.get('smtp_username')
    smtp_password = os.getenv('SMTP_PASSWORD') or config.get('smtp_password') # Prefer .env
    user_email = config.get('user_email')

    if not all([smtp_server, smtp_port, smtp_username, smtp_password, user_email]):
        print("Email alert configuration incomplete (SMTP server/port/user/pass/recipient).")
        return False

    # Create message
    msg = MIMEMultipart('alternative')
    subject = email_data.get('subject', 'N/S') # Use get with default
    msg['Subject'] = f"Urgent Email Alert: {subject}"
    msg['From'] = smtp_username
    msg['To'] = user_email

    # Create HTML content for the alert
    # Use .get() for potentially missing keys in email_data
    sender = email_data.get('from', 'N/A')
    summary = email_data.get('summary', 'No summary available')
    # Basic HTML escaping might be good for subject/sender/summary if they contain < or >
    # import html
    # summary = html.escape(summary) ... etc.

    html_content = f"""
    <html><head><style>body {{ font-family: Arial, sans-serif; }} .email-alert {{ border-left: 5px solid #e74c3c; padding: 15px; background-color: #fceded; border-radius: 4px; }}</style></head>
    <body>
      <h2>Urgent Email Alert</h2>
      <div class="email-alert">
        <p><strong>From:</strong> {sender}</p>
        <p><strong>Subject:</strong> {subject}</p>
        <p><strong>Summary:</strong> {summary}</p>
        <p><small>(This is an automated alert)</small></p>
      </div>
    </body></html>
    """
    # Create a simple text alternative
    text_content = f"""
    ** Urgent Email Alert **

    From: {sender}
    Subject: {subject}

    Summary: {summary}

    (This is an automated alert)
    """

    # Attach parts
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))

    # Send email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        print(f"Email alert sent for: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
         print("SMTP Authentication Error for Email Alert: Check username/password (use App Password for Gmail).")
         return False
    except Exception as e:
        print(f"Error sending email alert: {str(e)}")
        return False

def send_whatsapp_notification(email_data, config):
    """Sends a WhatsApp message. Can be an alert or a custom message (like --recent)."""
    if not TWILIO_AVAILABLE:
        # Print only if WhatsApp is actually enabled in config to avoid noise
        if config.get('notification_rules', {}).get('whatsapp_enabled'):
            print("Twilio library not installed (pip install twilio), cannot send WhatsApp.")
        return False

    # Check if WhatsApp is enabled in config
    if not config.get('notification_rules', {}).get('whatsapp_enabled'):
        # print("WhatsApp notifications are disabled in config.json.") # Can be noisy
        return False

    try:
        # Get credentials from .env
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        if not account_sid or not auth_token:
            print("Twilio credentials (SID/Token) not found in environment variables (.env).")
            return False

        # Get numbers from config
        from_whatsapp_number = config.get('twilio_whatsapp_number')
        to_whatsapp_number = config.get('user_whatsapp_number')
        if not from_whatsapp_number or not to_whatsapp_number:
            print("Twilio WhatsApp sender or recipient number not configured in config.json.")
            return False

        # --- Determine Message Body ---
        # Check if it's likely a recent summary report (long summary, no specific subject/from)
        summary_content = email_data.get('summary', 'No content provided.')
        is_report = "** Recent Email Summary" in summary_content or len(summary_content) > 300 # Heuristic

        if is_report:
            message_body = summary_content # Use the summary directly as the body
            print_subject = "Recent Summary Report"
        else:
            # Format as an alert for a single email
            sender = email_data.get('from', 'N/A')
            subject = email_data.get('subject', 'N/S')
            # Add category/score for context
            category = email_data.get('priority_category', '')
            score = email_data.get('priority_score', '')
            context = f" ({category.capitalize()}/{score})" if category and score else ""
            message_body = f"📧 *Email Alert*{context}\n*From:* {sender}\n*Subject:* {subject}\n\n{summary_content}"
            print_subject = subject # Subject for print statement

        # Ensure body isn't excessively long (though truncation happened before for --recent)
        max_len = 1600 # WhatsApp limit
        if len(message_body) > max_len:
             message_body = message_body[:max_len-40] + "\n... (truncated)"


        # Initialize Twilio client
        client = Client(account_sid, auth_token)

        # Send message
        message = client.messages.create(
            body=message_body,
            from_=f"whatsapp:{from_whatsapp_number}",
            to=f"whatsapp:{to_whatsapp_number}"
        )

        print(f"WhatsApp message sent for '{print_subject}'. SID: {message.sid}")
        return True

    except Exception as e:
        # Provide more context in the error message
        print(f"Error sending WhatsApp message (To: {config.get('user_whatsapp_number')} From: {config.get('twilio_whatsapp_number')} ): {str(e)}")
        # Check for common errors like 21211 (invalid number - often sandbox opt-in)
        if "21211" in str(e):
             print("  >> This might be Twilio Error 21211. Ensure the recipient has opted into your WhatsApp Sandbox by sending the join keyword.")
        elif "authenticate" in str(e).lower():
             print("  >> Check your Twilio Account SID and Auth Token in the .env file.")
        return False

def send_push_notification(email_data, config):
    """Sends a push notification via FCM."""
    if not FCM_AVAILABLE:
        if config.get('notification_rules', {}).get('push_enabled'):
             print("pyfcm library not installed (pip install pyfcm). Cannot send push notifications.")
        return False

    if not config.get('notification_rules', {}).get('push_enabled'):
        # print("Push notifications are disabled in config.json.")
        return False

    try:
        fcm_api_key = os.getenv("FCM_API_KEY")
        if not fcm_api_key:
            print("FCM API key not found in environment variables (.env).")
            return False

        device_tokens = config.get('device_tokens', [])
        if not device_tokens:
            # Be less verbose if push is disabled anyway
            # print("No device tokens configured in config.json for push notifications.")
            return False
        # Filter out empty strings/None from tokens list
        valid_tokens = [token for token in device_tokens if token]
        if not valid_tokens:
             print("No valid device tokens found in config.json.")
             return False


        push_service = FCMNotification(api_key=fcm_api_key)

        # Prepare notification data
        subject = email_data.get('subject', 'N/S')
        sender = email_data.get('from', 'N/A')
        summary = email_data.get('summary', 'No summary available')
        category = email_data.get('priority_category', 'N/A').capitalize()

        notification_title = f"{category}: {subject}"
        notification_body = f"From: {sender}\n{summary}"

        # Consider adding data payload if the receiving app needs more info
        # data_message = {
        #     "email_id": email_data.get('id'),
        #     "subject": subject,
        #      ...
        # }

        # Send notification
        result = push_service.notify_multiple_devices(
            registration_ids=valid_tokens,
            message_title=notification_title,
            message_body=notification_body
            # data_message=data_message # Optional data payload
        )

        # Check result for errors
        if result.get('failure', 0) > 0:
             print(f"Push notification failed for {result.get('failure')} devices. Results: {result.get('results')}")
             # Potentially handle cleaning up invalid tokens based on results
             return False
        elif result.get('success', 0) > 0:
             print(f"Push notification sent successfully to {result.get('success')} devices.")
             return True
        else:
            print(f"Push notification result unclear: {result}")
            return False


    except Exception as e:
        print(f"Error sending push notification: {str(e)}")
        return False

def send_notifications_for_batch(processed_emails, config):
    """
    Iterates through processed emails and sends configured notifications
    based on priority category and rules in config.json.
    """
    if not processed_emails: return # Nothing to do

    print(f"Checking {len(processed_emails)} processed emails for notifications...")
    rules = config.get('notification_rules', {})
    whatsapp_cats = rules.get('notify_whatsapp_for', ['critical'])
    push_cats = rules.get('notify_push_for', ['critical', 'high'])
    email_cats = rules.get('notify_email_for', ['critical']) # For specific alerts

    sent_count = 0
    # Use set to avoid duplicate notifications for same category if rules overlap
    notified_types = set()

    for email in processed_emails:
        category = email.get('priority_category', 'low')
        subject_print = email.get('subject', 'N/S')
        notified_types.clear() # Reset for each email

        try:
            # Determine which notifications apply (highest priority first maybe?)
            should_send_whatsapp = category in whatsapp_cats
            should_send_push = category in push_cats
            should_send_email = category in email_cats

            # Send only the highest priority applicable notification? Or all applicable?
            # Current logic sends all applicable ones that haven't been sent yet for this email.

            # WhatsApp Check
            if should_send_whatsapp and 'whatsapp' not in notified_types:
                print(f"-> Sending WhatsApp for '{subject_print}' (Category: {category})")
                if send_whatsapp_notification(email, config): # Pass config
                     sent_count += 1
                     notified_types.add('whatsapp') # Mark as sent

            # Push Check (use elif if only one notification type is desired)
            if should_send_push and 'push' not in notified_types:
                 print(f"-> Sending Push for '{subject_print}' (Category: {category})")
                 if send_push_notification(email, config): # Pass config
                     sent_count += 1
                     notified_types.add('push')

            # Email Alert Check
            if should_send_email and 'email_alert' not in notified_types:
                 print(f"-> Sending Email Alert for '{subject_print}' (Category: {category})")
                 if send_email_notification(email, config): # Pass config
                     sent_count += 1
                     notified_types.add('email_alert')

        except Exception as e:
             print(f"Error during notification dispatch for email {email.get('id', 'N/A')}: {e}")

    if sent_count > 0:
        print(f"Attempted to send {sent_count} immediate notifications.")
    else:
         print("No emails met criteria for immediate notification.")


# --- *** NEW Function for Generic Email Reports *** ---
def send_custom_email(subject, text_body, html_body, config):
    """Sends an email with custom subject and body content (e.g., for reports)."""
    # Get SMTP config details safely
    smtp_server = config.get('smtp_server')
    smtp_port = config.get('smtp_port')
    smtp_username = config.get('smtp_username')
    # IMPORTANT: Get password safely from .env preferred
    smtp_password = os.getenv('SMTP_PASSWORD') # Try .env first
    if not smtp_password:
        smtp_password = config.get('smtp_password') # Fallback to config
        if smtp_password:
             print("Warning: Using SMTP password from config.json. Store in .env as SMTP_PASSWORD for better security.")

    user_email = config.get('user_email') # Recipient email

    # Basic validation
    if not all([smtp_server, smtp_port, smtp_username, user_email]):
        print("Email configuration incomplete (SMTP server/port/user/recipient missing). Cannot send custom email.")
        return False
    if not smtp_password:
         print("Email configuration incomplete (SMTP password missing in .env or config). Cannot send custom email.")
         return False
    if not text_body and not html_body:
         print("Error: No text or HTML body provided for custom email.")
         return False


    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_username # Send from the configured user
    msg['To'] = user_email
    msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z") # Add Date header

    # Attach parts safely
    try:
        if text_body:
            msg.attach(MIMEText(text_body, 'plain', 'utf-8')) # Specify encoding
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8')) # Specify encoding
    except Exception as e:
         print(f"Error attaching email parts: {e}")
         return False

    # Send email
    server = None # Ensure server is defined for finally block
    try:
        print(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
        # Add timeout to SMTP connection
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.ehlo() # Greet server
        server.starttls() # Use TLS
        server.ehlo() # Greet again after TLS
        print("Logging into SMTP server...")
        server.login(smtp_username, smtp_password)
        print("Sending custom email...")
        server.send_message(msg)
        print(f"Custom email '{subject}' sent successfully to {user_email}.")
        return True
    except smtplib.SMTPAuthenticationError:
        print("SMTP Authentication Error: Check username/password (use App Password for Gmail).")
        return False
    except smtplib.SMTPConnectError:
         print(f"SMTP Connection Error: Could not connect to {smtp_server}:{smtp_port}.")
         return False
    except smtplib.SMTPServerDisconnected:
         print("SMTP Server Disconnected unexpectedly.")
         return False
    except TimeoutError:
         print("SMTP Connection timed out.")
         return False
    except Exception as e:
        print(f"Error sending custom email: {str(e)}")
        # import traceback # For detailed debug
        # traceback.print_exc() # For detailed debug
        return False
    finally:
        # Ensure server connection is closed
        if server:
            try:
                 server.quit()  
            except: # Ignore errors during quit
                 pass