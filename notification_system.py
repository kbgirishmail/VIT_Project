# notification_system.py
import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import requests
from dotenv import load_dotenv

# Attempt to import optional dependencies
TWILIO_AVAILABLE = False
FCM_AVAILABLE = False

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    pass

try:
    from pyfcm import FCMNotification
    FCM_AVAILABLE = True
except ImportError:
    pass

# Load environment variables
load_dotenv()

def load_config():
    """Load user configuration"""
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            return json.load(f)
    return {}

def send_email_notification(email_data, template="urgent"):
    """Send email notification for important emails"""
    config = load_config()
    
    # Check for required settings
    if not all(key in config for key in ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'user_email']):
        print("Email notification configuration incomplete")
        return False
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Urgent Email Alert: {email_data['subject']}"
    msg['From'] = config['smtp_username']
    msg['To'] = config['user_email']
    
    # Create HTML content
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .email-alert {{ border-left: 5px solid #ff0000; padding: 10px; }}
        </style>
    </head>
    <body>
        <h2>Urgent Email Alert</h2>
        <div class="email-alert">
            <p><strong>From:</strong> {email_data['from']}</p>
            <p><strong>Subject:</strong> {email_data['subject']}</p>
            <p><strong>Summary:</strong> {email_data.get('summary', 'No summary available')}</p>
            <p><a href="https://mail.google.com">View in Gmail</a></p>
        </div>
    </body>
    </html>
    """
    
    # Attach content
    msg.attach(MIMEText(html_content, 'html'))
    
    # Send email
    try:
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['smtp_username'], config['smtp_password'])
        server.send_message(msg)
        server.quit()
        print(f"Email notification sent for urgent message: {email_data['subject']}")
        return True
    except Exception as e:
        print(f"Error sending email notification: {str(e)}")
        return False

def send_whatsapp_notification(email_data):
    """Send WhatsApp message for critical emails"""
    if not TWILIO_AVAILABLE:
        print("Twilio not available. Install with: pip install twilio")
        return False
    
    try:
        # Get credentials
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            print("Twilio credentials not found in environment variables")
            return False
        
        client = Client(account_sid, auth_token)
        
        # Get WhatsApp numbers from config
        config = load_config()
        from_whatsapp_number = config.get('twilio_whatsapp_number')
        to_whatsapp_number = config.get('user_whatsapp_number')
        
        if not from_whatsapp_number or not to_whatsapp_number:
            print("WhatsApp numbers not configured")
            return False
        
        # Prepare message
        message_body = f"📧 *Urgent Email Alert*\n*From:* {email_data['from']}\n*Subject:* {email_data['subject']}\n\n{email_data.get('summary', 'No summary available')}"
        
        # Send message
        message = client.messages.create(
            body=message_body,
            from_=f"whatsapp:{from_whatsapp_number}",
            to=f"whatsapp:{to_whatsapp_number}"
        )
        
        print(f"WhatsApp message sent: {message.sid}")
        return True
    
    except Exception as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        return False

def send_push_notification(email_data):
    """Send push notification for critical emails"""
    if not FCM_AVAILABLE:
        print("Firebase Cloud Messaging not available. Install with: pip install pyfcm")
        return False
    
    try:
        fcm_api_key = os.getenv("FCM_API_KEY")
        if not fcm_api_key:
            print("FCM API key not found in environment variables")
            return False
        
        push_service = FCMNotification(api_key=fcm_api_key)
        
        # Get device tokens from config
        config = load_config()
        device_tokens = config.get('device_tokens', [])
        
        if not device_tokens:
            print("No device tokens configured for push notifications")
            return False
        
        # Prepare notification data
        notification_title = f"Urgent: {email_data['subject']}"
        notification_body = f"From: {email_data['from']}\n{email_data.get('summary', 'No summary available')}"
        
        # Send notification
        result = push_service.notify_multiple_devices(
            registration_ids=device_tokens,
            message_title=notification_title,
            message_body=notification_body
        )
        
        print(f"Push notification sent: {result}")
        return True
    
    except Exception as e:
        print(f"Error sending push notification: {str(e)}")
        return False

def handle_critical_email(email_data):
    """Process critical emails and send appropriate notifications"""
    config = load_config()
    priority_score = email_data.get('priority_score', 0)
    
    # Default thresholds
    push_threshold = config.get('notification_settings', {}).get('push_threshold', 50)
    whatsapp_threshold = config.get('notification_settings', {}).get('whatsapp_threshold', 75)
    
    # Always send email for critical emails
    if priority_score >= push_threshold:
        send_email_notification(email_data)
    
    # Send push notification if above threshold
    if priority_score >= push_threshold and FCM_AVAILABLE:
        send_push_notification(email_data)
    
    # Send WhatsApp if above threshold
    if priority_score >= whatsapp_threshold and TWILIO_AVAILABLE:
        send_whatsapp_notification(email_data)
    
    return True