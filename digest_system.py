# digest_system.py
import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# Try to import schedule (optional dependency)
SCHEDULE_AVAILABLE = False
try:
    import schedule
    import time
    SCHEDULE_AVAILABLE = True
except ImportError:
    pass

def load_config():
    """Load user configuration"""
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            return json.load(f)
    return {}

def format_digest_email(emails_by_priority, period="daily"):
    """Format email digest content"""
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            h1 {{ color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
            h2 {{ color: #3498db; margin-top: 20px; }}
            .email-summary {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; }}
            .priority-critical {{ border-left: 5px solid #e74c3c; }}
            .priority-high {{ border-left: 5px solid #f39c12; }}
            .priority-medium {{ border-left: 5px solid #3498db; }}
            .meta {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 5px; }}
            .summary {{ line-height: 1.5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Your {period.capitalize()} Email Digest</h1>
            <p>Here's a summary of your emails from {datetime.now().strftime('%Y-%m-%d')}:</p>
    """
    
    # Add critical emails
    if emails_by_priority.get('critical'):
        html_content += "<h2>Critical Emails</h2>"
        for email in emails_by_priority['critical']:
            html_content += f"""
            <div class="email-summary priority-critical">
                <div class="meta"><strong>From:</strong> {email['from']}</div>
                <div class="meta"><strong>Subject:</strong> {email['subject']}</div>
                <div class="meta"><strong>Time:</strong> {email.get('date', 'Unknown')}</div>
                <div class="summary"><strong>Summary:</strong> {email.get('summary', 'No summary available')}</div>
            </div>
            """
    
    # Add high priority emails
    if emails_by_priority.get('high'):
        html_content += "<h2>High Priority</h2>"
        for email in emails_by_priority['high']:
            html_content += f"""
            <div class="email-summary priority-high">
                <div class="meta"><strong>From:</strong> {email['from']}</div>
                <div class="meta"><strong>Subject:</strong> {email['subject']}</div>
                <div class="meta"><strong>Time:</strong> {email.get('date', 'Unknown')}</div>
                <div class="summary"><strong>Summary:</strong> {email.get('summary', 'No summary available')}</div>
            </div>
            """
    
    # Add medium priority emails (only for daily digest)
    if period == "daily" and emails_by_priority.get('medium'):
        html_content += "<h2>Medium Priority</h2>"
        for email in emails_by_priority['medium']:
            html_content += f"""
            <div class="email-summary priority-medium">
                <div class="meta"><strong>From:</strong> {email['from']}</div>
                <div class="meta"><strong>Subject:</strong> {email['subject']}</div>
                <div class="meta"><strong>Time:</strong> {email.get('date', 'Unknown')}</div>
                <div class="summary"><strong>Summary:</strong> {email.get('summary', 'No summary available')}</div>
            </div>
            """
    
    # Close HTML
    html_content += """
        </div>
    </body>
    </html>
    """
    
    return html_content

def send_email_digest(emails_by_priority, period="daily"):
    """Send digest email with formatted summaries"""
    config = load_config()
    
    # Check for required settings
    if not all(key in config for key in ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'user_email']):
        print("Email digest configuration incomplete")
        return False
    
    # Skip if no emails to report
    if not any(emails_by_priority.values()):
        print(f"No emails to include in {period} digest")
        return False
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Your {period.capitalize()} Email Digest"
    msg['From'] = config['smtp_username']
    msg['To'] = config['user_email']
    
    # Format digest content
    html_content = format_digest_email(emails_by_priority, period)
    
    # Attach HTML content
    msg.attach(MIMEText(html_content, 'html'))
    
    # Send email
    try:
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['smtp_username'], config['smtp_password'])
        server.send_message(msg)
        server.quit()
        print(f"{period.capitalize()} digest email sent successfully.")
        return True
    except Exception as e:
        print(f"Error sending digest email: {str(e)}")
        return False

def run_digest(period="daily", days=1):
    """Run email digest process"""
    from email_fetcher import fetch_emails_since  # Import here to avoid circular imports
    from priority_system import categorize_emails
    
    print(f"Generating {period} digest...")
    
    # Fetch emails from the past X days
    emails = fetch_emails_since(days=days)
    
    if not emails:
        print(f"No emails found for {period} digest")
        return False
    
    # Make sure all emails have summaries
    for email in emails:
        if 'content' in email and not 'summary' in email:
            # Use existing summarization function - modify based on your codebase
            from gemini_api_summary import summarize_with_gemini
            email['summary'] = summarize_with_gemini(email['content'], email['subject'])
    
    # Categorize emails by priority
    emails_by_priority = categorize_emails(emails)
    
    # For weekly digest, only include high priority and above
    if period == "weekly":
        emails_by_priority['medium'] = []
        emails_by_priority['low'] = []
    
    # Send digest
    return send_email_digest(emails_by_priority, period)

def setup_scheduled_digests():
    """Set up scheduled runs for email digests"""
    if not SCHEDULE_AVAILABLE:
        print("Schedule module not available. Install with: pip install schedule")
        return False
    
    config = load_config()
    
    # Get schedule settings from config or use defaults
    daily_time = config.get('daily_digest_time', '17:00')
    weekly_day = config.get('weekly_digest_day', 'monday').lower()
    weekly_time = config.get('weekly_digest_time', '09:00')
    
    # Set up daily digest
    schedule.every().day.at(daily_time).do(lambda: run_digest(period="daily", days=1))
    print(f"Daily digest scheduled for {daily_time}")
    
    # Set up weekly digest
    if weekly_day == 'monday':
        schedule.every().monday.at(weekly_time).do(lambda: run_digest(period="weekly", days=7))
    elif weekly_day == 'tuesday':
        schedule.every().tuesday.at(weekly_time).do(lambda: run_digest(period="weekly", days=7))
    elif weekly_day == 'wednesday':
        schedule.every().wednesday.at(weekly_time).do(lambda: run_digest(period="weekly", days=7))
    elif weekly_day == 'thursday':
        schedule.every().thursday.at(weekly_time).do(lambda: run_digest(period="weekly", days=7))
    elif weekly_day == 'friday':
        schedule.every().friday.at(weekly_time).do(lambda: run_digest(period="weekly", days=7))
    elif weekly_day == 'saturday':
        schedule.every().saturday.at(weekly_time).do(lambda: run_digest(period="weekly", days=7))
    elif weekly_day == 'sunday':
        schedule.every().sunday.at(weekly_time).do(lambda: run_digest(period="weekly", days=7))
    
    print(f"Weekly digest scheduled for {weekly_day.capitalize()} at {weekly_time}")
    
    # Run scheduler loop
    print("Starting scheduled digest service...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute