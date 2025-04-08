# email_system_integration.py
"""
Integration module for the LLM-Powered Email Assistant System.
This module connects the various components of the system.
"""

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def initialize_system():
    """Initialize the email assistant system"""
    # Check for required files
    required_files = ['credentials.json']
    for file in required_files:
        if not os.path.exists(file):
            print(f"Error: Required file {file} not found.")
            print("Please ensure you have the proper Google API credentials file.")
            return False
    
    # Check for configuration
    if not os.path.exists('config.json'):
        print("Configuration file not found. Running setup...")
        from smart_email_assistant import setup_config
        setup_config()
    
    # Verify environment variables
    required_env_vars = ['API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Some features may not work properly.")
    
    # Optional environment variables
    optional_env_vars = {
        'TWILIO_ACCOUNT_SID': 'WhatsApp notifications',
        'TWILIO_AUTH_TOKEN': 'WhatsApp notifications',
        'FCM_API_KEY': 'Push notifications'
    }
    
    for var, feature in optional_env_vars.items():
        if not os.getenv(var):
            print(f"Note: {var} not found. {feature} will be unavailable.")
    
    # Verify dependencies
    try:
        import google.oauth2.credentials
        import google_auth_oauthlib.flow
        import googleapiclient.discovery
        import bs4
        print("Core dependencies verified.")
    except ImportError as e:
        print(f"Error: Missing core dependency: {str(e)}")
        print("Please install required packages: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 beautifulsoup4 python-dotenv")
        return False
    
    # Check optional dependencies
    optional_deps = [
        ('schedule', 'Scheduled digests'),
        ('twilio', 'WhatsApp notifications'),
        ('pyfcm', 'Push notifications'),
        ('google.generativeai', 'Gemini API summarization')
    ]
    
    for module, feature in optional_deps:
        try:
            __import__(module)
            print(f"✓ {feature} support available")
        except ImportError:
            print(f"✗ {feature} support unavailable (missing {module})")
    
    return True

def summarize_email(email_content, subject=""):
    """Unified interface for email summarization that tries available methods"""
    try:
        # Try Gemini API first
        try:
            from gemini_api_summary import summarize_with_gemini
            return summarize_with_gemini(email_content, subject)
        except ImportError:
            pass
        
        # Try transformer-based summarization
        try:
            from bs_summary_v2 import summarize_email
            return summarize_email(email_content)
        except ImportError:
            pass
        
        # Fallback to basic summarization
        return basic_summarize(email_content)
    except Exception as e:
        print(f"Error during summarization: {str(e)}")
        return "Error generating summary."

def basic_summarize(text, max_length=150):
    """Basic fallback summarization method"""
    # Simple extractive summarization
    if len(text) <= max_length:
        return text
    
    # Get first few sentences
    sentences = text.split('.')
    summary = ""
    for sentence in sentences:
        if len(summary) + len(sentence) < max_length:
            summary += sentence + "."
        else:
            break
    
    return summary.strip()

def monitor_emails_integrated():
    """Integrated email monitoring function"""
    # Import required modules
    from email_fetcher import fetch_emails_since
    from priority_system import calculate_priority, categorize_emails
    from notification_system import handle_critical_email
    
    # Setup monitoring and notification process
    processed_ids = set()
    
    def check_new_emails():
        try:
            # Fetch recent emails (last hour)
            emails = fetch_emails_since(days=0.04)  # ~1 hour
            
            if not emails:
                return []
            
            new_emails = [e for e in emails if e['id'] not in processed_ids]
            for email in new_emails:
                processed_ids.add(email['id'])
                
                # Generate summary if not present
                if 'content' in email and not 'summary' in email:
                    email['summary'] = summarize_email(email['content'], email['subject'])
                
                # Calculate priority
                email['priority_score'] = calculate_priority(email)
            
            return new_emails
        except Exception as e:
            print(f"Error checking new emails: {str(e)}")
            return []
    
    def process_critical_emails(emails):
        """Process emails and handle critical ones"""
        critical_count = 0
        for email in emails:
            if email['priority_score'] >= 50:  # Critical threshold
                handle_critical_email(email)
                critical_count += 1
        
        return critical_count
    
    return check_new_emails, process_critical_emails

# Example usage function to demonstrate the system
def demo_email_processing(num_emails=5):
    """Demo function to show the email processing system in action"""
    from email_fetcher import fetch_emails_since
    from priority_system import categorize_emails
    
    print(f"Fetching {num_emails} recent emails for demonstration...")
    emails = fetch_emails_since(days=7, max_results=num_emails)
    
    if not emails:
        print("No emails found for demonstration.")
        return
    
    print(f"Found {len(emails)} emails. Processing...")
    
    # Process each email
    for email in emails:
        print(f"\nProcessing email: {email['subject']}")
        
        # Generate summary
        if 'content' in email:
            print("Generating summary...")
            email['summary'] = summarize_email(email['content'], email['subject'])
            print(f"Summary: {email['summary'][:100]}...")
        
        # Calculate priority
        from priority_system import calculate_priority
        email['priority_score'] = calculate_priority(email)
        print(f"Priority score: {email['priority_score']}")
        
        # Determine notification levels
        if email['priority_score'] >= 75:
            print("ACTION: Would send WhatsApp notification (critical)")
        elif email['priority_score'] >= 50:
            print("ACTION: Would send push notification (high priority)")
        elif email['priority_score'] >= 30:
            print("ACTION: Would include in daily digest (medium priority)")
    
    # Show categorized results
    print("\nEmail categorization results:")
    categories = categorize_emails(emails)
    for category, emails_list in categories.items():
        print(f"- {category.capitalize()}: {len(emails_list)} emails")

if __name__ == "__main__":
    if initialize_system():
        print("\nSystem initialized successfully!")
        print("You can now run the assistant using the smart_email_assistant.py script.")
        print("\nExample commands:")
        print("  Process emails:  python smart_email_assistant.py --process --count 10")
        print("  Start monitoring: python smart_email_assistant.py --monitor")
        print("  Run daily digest: python smart_email_assistant.py --run-digest daily")
        print("  Start all services: python smart_email_assistant.py --all")
        
        # Uncomment to run a demo
        # demo_email_processing(3)
    else:
        print("\nSystem initialization failed. Please resolve the issues above.")