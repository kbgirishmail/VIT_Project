# smart_email_assistant.py
import argparse
import threading
import sys
import os
import json
import time

def setup_config():
    """Set up configuration file if it doesn't exist"""
    if not os.path.exists('config.json'):
        config = {
            "user_email": input("Enter your email address: "),
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": input("Enter your SMTP username (usually your email): "),
            "smtp_password": input("Enter your app password for email: "),
            "vip_contacts": [],
            "custom_keywords": [],
            "notification_settings": {
                "push_threshold": 50,
                "whatsapp_threshold": 75
            },
            "daily_digest_time": "17:00",
            "weekly_digest_day": "monday",
            "weekly_digest_time": "09:00",
            "device_tokens": []
        }
        
        print("\nWould you like to configure WhatsApp notifications? (y/n)")
        if input().lower() == 'y':
            config["twilio_whatsapp_number"] = input("Enter your Twilio WhatsApp number: ")
            config["user_whatsapp_number"] = input("Enter your WhatsApp number: ")
        
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        
        print("\nConfiguration saved. Please set up your environment variables in a .env file:")
        print("API_KEY=your-gemini-api-key")
        print("TWILIO_ACCOUNT_SID=your-twilio-account-sid (if using WhatsApp)")
        print("TWILIO_AUTH_TOKEN=your-twilio-auth-token (if using WhatsApp)")
        print("FCM_API_KEY=your-firebase-cloud-messaging-api-key (if using push notifications)")
        
        return True
    return False

def start_email_monitoring():
    """Start continuous email monitoring for real-time notifications"""
    try:
        from email_fetcher import fetch_emails_since
        from priority_system import categorize_emails
        from notification_system import handle_critical_email
        
        print("Starting real-time email monitoring...")
        
        # Try importing summarization module
        try:
            from gemini_api_summary import summarize_with_gemini as summarize
        except ImportError:
            try:
                from bs_summary_v2 import summarize_email as summarize
            except ImportError:
                def summarize(content, subject):
                    return "Summary not available (summarization module not found)"
        
        # Keep track of processed emails
        processed_ids = set()
        
        while True:
            try:
                # Fetch recent emails (last hour)
                print("\nChecking for new emails...")
                emails = fetch_emails_since(days=0.04)  # ~1 hour
                
                if not emails:
                    print("No new emails found.")
                else:
                    print(f"Found {len(emails)} recent emails, checking for new ones...")
                    new_emails = [e for e in emails if e['id'] not in processed_ids]
                    
                    if not new_emails:
                        print("No new unprocessed emails.")
                    else:
                        print(f"Processing {len(new_emails)} new emails...")
                        
                        for email in new_emails:
                            # Add to processed list
                            processed_ids.add(email['id'])
                            
                            # Generate summary if not present
                            if 'content' in email and not 'summary' in email:
                                email['summary'] = summarize(email['content'], email['subject'])
                            
                            # Calculate priority and check if critical
                            from priority_system import calculate_priority
                            email['priority_score'] = calculate_priority(email)
                            
                            # Handle notifications for critical emails
                            if email['priority_score'] >= 50:
                                print(f"Critical email detected: {email['subject']}")
                                handle_critical_email(email)
                
                # Limit size of processed IDs to prevent memory issues
                if len(processed_ids) > 1000:
                    processed_ids = set(list(processed_ids)[-500:])
                
                # Wait before next check
                print("Waiting for new emails...")
                time.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                print(f"Error during email monitoring: {str(e)}")
                time.sleep(300)  # If error, wait 5 minutes before retry
                
    except ImportError as e:
        print(f"Required module not found: {str(e)}")
        print("Please ensure all dependencies are installed.")
        return False
    except Exception as e:
        print(f"Error starting email monitoring: {str(e)}")
        return False

def start_digest_service():
    """Start scheduled digest service"""
    try:
        from digest_system import setup_scheduled_digests
        
        # Start in a separate thread
        digest_thread = threading.Thread(target=setup_scheduled_digests)
        digest_thread.daemon = True
        digest_thread.start()
        
        return True
    except ImportError as e:
        print(f"Required module not found: {str(e)}")
        print("Please ensure all dependencies are installed.")
        return False
    except Exception as e:
        print(f"Error starting digest service: {str(e)}")
        return False
        
def process_batch_emails(count=10):
    """Process a batch of emails with priority and notifications"""
    try:
        from email_fetcher import fetch_emails_since
        from priority_system import categorize_emails
        from notification_system import handle_critical_email
        
        # Try importing summarization module
        try:
            from gemini_api_summary import summarize_with_gemini as summarize
        except ImportError:
            try:
                from bs_summary_v2 import summarize_email as summarize
            except ImportError:
                def summarize(content, subject):
                    return "Summary not available (summarization module not found)"
        
        print(f"Fetching and processing the latest {count} emails...")
        emails = fetch_emails_since(days=7, max_results=count)
        
        if not emails:
            print("No emails found.")
            return False
        
        print(f"Found {len(emails)} emails. Processing...")
        
        for email in emails:
            # Generate summary if not present
            if 'content' in email and not 'summary' in email:
                print(f"Summarizing: {email['subject']}")
                email['summary'] = summarize(email['content'], email['subject'])
            
            # Calculate priority
            from priority_system import calculate_priority
            email['priority_score'] = calculate_priority(email)
            
            # Handle notifications for critical emails
            if email['priority_score'] >= 50:
                print(f"Critical email detected: {email['subject']}")
                handle_critical_email(email)
        
        # Categorize emails
        categorized = categorize_emails(emails)
        
        # Print results
        print("\nEmail Processing Results:")
        print(f"Critical priority: {len(categorized['critical'])}")
        print(f"High priority: {len(categorized['high'])}")
        print(f"Medium priority: {len(categorized['medium'])}")
        print(f"Low priority: {len(categorized['low'])}")
        
        return True
    
    except ImportError as e:
        print(f"Required module not found: {str(e)}")
        print("Please ensure all dependencies are installed.")
        return False
    except Exception as e:
        print(f"Error processing emails: {str(e)}")
        return False

def run_single_digest(period="daily"):
    """Run a single digest operation"""
    try:
        from digest_system import run_digest
        
        days = 1 if period == "daily" else 7
        return run_digest(period=period, days=days)
        
    except ImportError as e:
        print(f"Required module not found: {str(e)}")
        print("Please ensure all dependencies are installed.")
        return False
    except Exception as e:
        print(f"Error running digest: {str(e)}")
        return False


from twilio.rest import Client
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

def test_whatsapp_notification():
    try:
        # Get Twilio credentials from environment variables
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")  # Add this to your .env
        user_whatsapp_number = os.getenv("USER_WHATSAPP_NUMBER")      # Add this to your .env

        # Check if all required variables are set
        if not all([account_sid, auth_token, twilio_whatsapp_number, user_whatsapp_number]):
            raise ValueError("Missing required environment variables. Check your .env file.")

        # Initialize Twilio client
        client = Client(account_sid, auth_token)

        # Send WhatsApp message
        message = client.messages.create(
            from_=f"whatsapp:{twilio_whatsapp_number}",
            body="Test WhatsApp notification!",
            to=f"whatsapp:{user_whatsapp_number}"
        )
        print(f"Message sent successfully! SID: {message.sid}")

    except Exception as e:
        print(f"Failed to send WhatsApp message: {str(e)}")


def main():
    test_whatsapp_notification()
    """Main function to parse arguments and start the application"""
    parser = argparse.ArgumentParser(description="LLM-Powered Email Assistant")
    parser.add_argument("-p", "--process", action="store_true", help="Process emails in inbox")
    parser.add_argument("-m", "--monitor", action="store_true", help="Start real-time email monitoring")
    parser.add_argument("-d", "--digests", action="store_true", help="Start scheduled email digests")
    parser.add_argument("-c", "--count", type=int, default=10, help="Number of emails to process")
    parser.add_argument("--config", action="store_true", help="Set up configuration")
    parser.add_argument("--run-digest", choices=["daily", "weekly"], help="Run a single digest operation")
    parser.add_argument("--all", action="store_true", help="Run all services (monitoring and digests)")
    
    args = parser.parse_args()
    
    # Check if any argument was provided
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    # Setup configuration if requested or if it doesn't exist
    if args.config or not os.path.exists('config.json'):
        setup_config()
    
    # Start services based on arguments
    if args.all:
        monitoring_thread = threading.Thread(target=start_email_monitoring)
        monitoring_thread.daemon = True
        monitoring_thread.start()
        
        digest_thread = threading.Thread(target=start_digest_service)
        digest_thread.daemon = True
        digest_thread.start()
        
        print("All services started. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting...")
            return
    
    if args.monitor:
        print("Starting email monitoring service...")
        start_email_monitoring()
    
    if args.digests:
        print("Starting scheduled digest service...")
        start_digest_service()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting digest service...")
            return
    
    if args.process:
        process_batch_emails(args.count)
    
    if args.run_digest:
        print(f"Running a single {args.run_digest} digest...")
        run_single_digest(args.run_digest)

if __name__ == "__main__":
    main()