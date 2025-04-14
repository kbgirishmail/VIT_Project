# smart_email_assistant.py
import argparse
import threading
import sys
import os
import json
import time
from datetime import datetime # Added for timestamp printing

# Import your modules (at the top level)
try:
    import email_fetcher
    import llm_handler # Renamed from gemini_api_summary
    import priority_system
    import notification_system # Import the module itself
    import digest_system
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Fatal Error: Missing required module - {e}")
    print("Please ensure all project files (email_fetcher.py, llm_handler.py, etc.) exist and dependencies are installed.")
    sys.exit(1)

# --- Configuration ---
CONFIG_FILE = 'config.json'
ENV_FILE = '.env' # Make sure you have a .env file for API keys
PROCESSED_IDS_FILE = 'processed_email_ids.json' # Added for persistence
LAST_CHECK_FILE = 'last_check_timestamp.txt' # Added for persistence

# --- Config Setup ---
# Keep setup_config() function as is
def setup_config():
    """Set up configuration file if it doesn't exist"""
    if not os.path.exists('config.json'):
        config = {
            "user_email": input("Enter your email address: "),
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": input("Enter your SMTP username (usually your email): "),
            "smtp_password": input("Enter your app password for email: "), # Advise storing in .env
            "vip_contacts": [],
            "custom_keywords": ["urgent", "important", "deadline"], # Add some defaults
            "notification_rules": {
                "whatsapp_enabled": False,
                "push_enabled": False,
                "email_enabled": False,
                "notify_whatsapp_for": ["critical"],
                "notify_push_for": ["critical", "high"],
                "notify_email_for": ["critical"]
            },
            "notification_settings": { # Keep for backward compatibility or merge into rules
                 "push_threshold": 50, # Priority score threshold for push
                 "whatsapp_threshold": 75 # Priority score threshold for WhatsApp/Critical
             },
             "check_interval_seconds": 300, # Default monitor check interval
            "daily_digest_time": "17:00",
            "weekly_digest_day": "monday",
            "weekly_digest_time": "09:00",
            "device_tokens": [],
            "twilio_whatsapp_number": "", # Initialize empty
            "user_whatsapp_number": "" # Initialize empty
        }

        print("\nWould you like to configure WhatsApp notifications? (y/n)")
        if input().lower() == 'y':
            config["twilio_whatsapp_number"] = input("Enter your Twilio WhatsApp number (e.g., +14155238886): ")
            config["user_whatsapp_number"] = input("Enter YOUR WhatsApp number (e.g., +919876543210): ")
            config["notification_rules"]["whatsapp_enabled"] = True

        print("\nWould you like to configure Email alerts for critical emails? (y/n)")
        if input().lower() == 'y':
             config["notification_rules"]["email_enabled"] = True

        # Add similar setup for Push Notifications (FCM) if needed

        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)

        print("\nConfiguration saved to config.json.")
        print("IMPORTANT: Ensure you have a .env file in the same directory with:")
        print("API_KEY=your-gemini-api-key")
        print("TWILIO_ACCOUNT_SID=your-twilio-account-sid (if using WhatsApp)")
        print("TWILIO_AUTH_TOKEN=your-twilio-auth-token (if using WhatsApp)")
        print("FCM_API_KEY=your-firebase-cloud-messaging-api-key (if using push notifications)")
        print("Consider adding SMTP_PASSWORD=your-email-app-password to .env for security instead of config.json.")

        return True
    return False

# --- Utility Functions for Persistence ---
def load_config():
    """Loads configuration from JSON file."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: Configuration file '{CONFIG_FILE}' not found.")
        if setup_config():
             print("Please re-run the script.")
        sys.exit(1)
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{CONFIG_FILE}'. Check its format.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

def load_processed_ids():
    """Loads the set of processed email IDs from a file."""
    if os.path.exists(PROCESSED_IDS_FILE):
        try:
            with open(PROCESSED_IDS_FILE, 'r') as f:
                content = f.read()
                if not content: return set()
                return set(json.loads(content))
        except json.JSONDecodeError:
            print(f"Warning: Could not read '{PROCESSED_IDS_FILE}'. Starting with empty set.")
            return set()
        except Exception as e:
             print(f"Warning: Error loading processed IDs: {e}. Starting with empty set.")
             return set()
    return set()

def save_processed_ids(ids_set):
    """Saves the set of processed email IDs to a file."""
    try:
        with open(PROCESSED_IDS_FILE, 'w') as f:
            json.dump(list(ids_set), f)
    except Exception as e:
        print(f"Error saving processed IDs: {e}")

def get_last_check_time():
    """Gets the timestamp of the last check from a file."""
    if os.path.exists(LAST_CHECK_FILE):
        try:
            with open(LAST_CHECK_FILE, 'r') as f:
                return float(f.read().strip())
        except ValueError:
             print(f"Warning: Invalid timestamp in {LAST_CHECK_FILE}. Fetching more emails.")
             return None
        except Exception as e:
            print(f"Warning: Could not read last check time: {e}. Fetching more emails initially.")
            return None
    return None

def save_last_check_time(timestamp):
    """Saves the timestamp of the current check."""
    try:
        with open(LAST_CHECK_FILE, 'w') as f:
            f.write(str(timestamp))
    except Exception as e:
        print(f"Error saving last check time: {e}")

# --- Core Processing Function ---
def process_single_email(raw_email, config):
    """Processes a single raw email dict, adding LLM results and priority."""
    # --- REMOVED Debug Print ---
    print(f"DEBUG: Type of raw_email in process_single_email: {type(raw_email)}")
    if not isinstance(raw_email, dict):
        print(f"DEBUG: Value of raw_email (when not dict): {raw_email}")
    # --- End Removed Debug Print ---

    # Check if raw_email is a dictionary before proceeding
    if not isinstance(raw_email, dict):
        print(f"!! Error: Expected a dictionary for email data, but got {type(raw_email)}. Skipping.")
        # Return a structure indicating error, or None
        return {'id': None, 'subject': 'Processing Error', 'error': f'Invalid data type: {type(raw_email)}'}

    email_id_print = raw_email.get('id', 'N/A')
    subject_print = raw_email.get('subject', 'N/S')
    print(f"Processing email - ID: {email_id_print}, Subject: {subject_print}")

    processed_data = raw_email.copy() # Work on a copy
    content = processed_data.get('content', '')
    subject = processed_data.get('subject', '')

    # --- LLM Analysis Steps ---
    llm_error = False
    try:
        # 1. Summarize
        summary_result = llm_handler.summarize_email(content, subject)
        processed_data['summary'] = summary_result
        if summary_result.startswith("Error:"): llm_error = True

        # 2. Classify
        classify_result = llm_handler.classify_email(content, subject)
        processed_data['classification'] = classify_result
        if classify_result.startswith("Error:"): llm_error = True

        # 3. Intent & Sentiment
        intent, sentiment = llm_handler.detect_intent_and_sentiment(content)
        processed_data['intent'] = intent
        processed_data['sentiment'] = sentiment
        if intent.startswith("Error:") or sentiment.startswith("Error:"): llm_error = True

        # 4. Action Items
        action_items_result = llm_handler.extract_action_items(content)
        processed_data['action_items'] = action_items_result
        # Check if the list contains an error string
        if action_items_result and isinstance(action_items_result, list) and action_items_result[0].startswith("Error:"):
             llm_error = True

        # 5. Smart Replies (Optional)
        # reply_result = llm_handler.suggest_replies(processed_data['summary'])
        # processed_data['smart_replies'] = reply_result
        # if reply_result and isinstance(reply_result, list) and reply_result[0].startswith("Error:"):
        #      llm_error = True

        # --- Priority Calculation ---
        # Calculate priority even if LLM had errors, might use other factors
        priority_system.calculate_priority(processed_data, config)

        # --- Determine Priority Category ---
        score = processed_data.get('priority_score', 0)
        settings = config.get('notification_settings', {})
        critical_threshold = settings.get('whatsapp_threshold', 75)
        high_threshold = settings.get('push_threshold', 50)
        medium_threshold = 20
        category = 'low'
        if score >= critical_threshold: category = 'critical'
        elif score >= high_threshold: category = 'high'
        elif score >= medium_threshold: category = 'medium'
        processed_data['priority_category'] = category

        # --- Print Summary ---
        print(f"  -> Summary: {processed_data.get('summary', 'N/A')[:70]}...")
        print(f"  -> Classification: {processed_data.get('classification', 'N/A')}")
        print(f"  -> Intent: {processed_data.get('intent', 'N/A')}, Sentiment: {processed_data.get('sentiment', 'N/A')}")
        print(f"  -> Priority: {processed_data.get('priority_score', 'N/A')} ({processed_data.get('priority_category', 'N/A')})")
        if llm_error: print("  -> !! Note: One or more LLM calls failed for this email.")

    except Exception as e:
        # Catch unexpected errors during the processing steps
        print(f"!! Unhandled error during processing email ID {email_id_print}: {e}")
        # Set error state more explicitly
        processed_data['summary'] = processed_data.get('summary', 'Processing Error')
        processed_data['classification'] = processed_data.get('classification', 'Error')
        processed_data['priority_score'] = processed_data.get('priority_score', 0) # Keep score if calculated before error
        processed_data['priority_category'] = 'Error' # Specific error category
        processed_data['error'] = str(e) # Store the error message

    return processed_data

# --- Modes of Operation ---

# --- Keep start_email_monitoring as is ---
def start_email_monitoring(config):
    """Start continuous email monitoring for real-time notifications"""
    print("Starting real-time email monitoring...")
    processed_ids = load_processed_ids()
    check_interval = config.get('check_interval_seconds', 300) # Default 5 minutes

    while True:
        start_time = time.time()
        current_dt_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[{current_dt_str}] Checking for new emails...")

        last_check_ts = get_last_check_time()
        if last_check_ts:
             seconds_since_last = max(0, time.time() - last_check_ts)
             fetch_since_ts = last_check_ts - 60 # Go back 1 minute
             query = f"after:{int(fetch_since_ts)}"
             print(f"Fetching emails since {datetime.fromtimestamp(fetch_since_ts).strftime('%Y-%m-%d %H:%M:%S')}")
             days_to_fetch = None
        else:
             print("First run or missing last check time. Fetching recent emails (last ~4 hours).")
             query = None
             days_to_fetch = 0.17 # Approx 4 hours

        try:
            raw_emails = email_fetcher.fetch_emails_since(days=days_to_fetch, query=query, max_results=30)
            print(f"Fetched {len(raw_emails)} emails.")

            new_emails_to_process = []
            for raw_email in raw_emails:
                # Basic check if raw_email is a dictionary before accessing 'id'
                if isinstance(raw_email, dict):
                     email_id = raw_email.get('id')
                     if email_id and email_id not in processed_ids:
                         new_emails_to_process.append(raw_email)
                else:
                     print(f"Warning: Received non-dictionary item from fetcher: {type(raw_email)}. Skipping.")


            if not new_emails_to_process:
                 print("No new unprocessed emails found.")
            else:
                print(f"Found {len(new_emails_to_process)} new emails to process.")
                processed_this_cycle = []
                for raw_email in new_emails_to_process:
                     processed_email = process_single_email(raw_email, config)
                     # Check if processing failed badly before adding ID
                     if processed_email.get('id'): # Only add if ID is still there
                          processed_this_cycle.append(processed_email)
                          processed_ids.add(processed_email['id']) # Add ID after processing attempt

                if processed_this_cycle:
                    print(f"Sending notifications for {len(processed_this_cycle)} successfully processed emails...")
                    notification_system.send_notifications_for_batch(processed_this_cycle, config)
                else:
                    print("No emails were successfully processed in this cycle.")

            save_processed_ids(processed_ids)
            if len(processed_ids) > 2000:
                print("Trimming processed IDs history...")
                processed_ids = set(list(processed_ids)[-1500:])
                save_processed_ids(processed_ids)

            save_last_check_time(start_time)

        except Exception as e:
            print(f"!! Error during monitoring cycle: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for monitor errors

        elapsed_time = time.time() - start_time
        sleep_time = max(15, check_interval - elapsed_time)
        print(f"Cycle finished in {elapsed_time:.2f}s. Sleeping for {sleep_time:.2f}s...")
        time.sleep(sleep_time)

# --- Keep start_digest_service as is ---
def start_digest_service(config):
    """Start scheduled digest service"""
    try:
        import schedule
        print("Attempting to start scheduled digest service...")
        # Ensure setup_scheduled_digests accepts config
        digest_system.setup_scheduled_digests(config) # Pass config
        print("Digest service scheduler setup complete (runs based on schedule).")
        return True
    except ImportError:
        print("Module 'schedule' not found. Install with: pip install schedule")
        print("Scheduled digests disabled.")
        return False
    except Exception as e:
        print(f"Error starting digest service: {str(e)}")
        return False

# --- Keep process_batch_emails as is ---
def process_batch_emails(config, count=10):
    """Process a batch of recent emails (no real-time alerts)"""
    print(f"Fetching and processing the latest {count} emails...")
    try:
        raw_emails = email_fetcher.fetch_emails_since(query="in:inbox", max_results=count)

        if not raw_emails:
            print("No emails found.")
            return False

        print(f"Found {len(raw_emails)} emails. Processing...")
        processed_list = []
        for email in raw_emails:
            processed_email = process_single_email(email, config)
            processed_list.append(processed_email)

        categorized = priority_system.categorize_emails(processed_list, config)

        print("\n--- Batch Processing Results ---")
        for category, email_list in categorized.items():
            print(f"{category.capitalize()} priority: {len(email_list)} emails")
        print("------------------------------")
        return True
    except Exception as e:
        print(f"Error processing batch emails: {str(e)}")
        return False

# --- Keep run_single_digest as is ---
def run_single_digest(config, period="daily"):
    """Run a single digest operation"""
    print(f"Manually running {period} digest...")
    try:
        success = digest_system.run_digest(config, period=period, days=(1 if period == "daily" else 7))
        if success: print(f"{period.capitalize()} digest run completed successfully.")
        else: print(f"{period.capitalize()} digest run failed.")
        return success
    except Exception as e:
        print(f"Error running digest: {str(e)}")
        return False

# --- Keep test_whatsapp_notification as is ---
def test_whatsapp_notification(config):
    """Sends a test WhatsApp message using config."""
    if not notification_system.TWILIO_AVAILABLE:
         print("Twilio library not installed (pip install twilio). Cannot send test.")
         return
    print("Attempting to send test WhatsApp message...")
    test_data = { 'from': 'Test Sender', 'subject': 'WhatsApp Test', 'summary': 'Test from Email Assistant.' }
    try:
         success = notification_system.send_whatsapp_notification(test_data, config)
         if success: print("Test WhatsApp message function executed. Check your phone.")
         else: print("Test WhatsApp message function reported failure. See previous errors.")
    except Exception as e:
        print(f"Error calling test_whatsapp_notification: {e}")


# --- Updated Function for Recent Summary ---
def send_recent_summary(config, count):
    """Fetches, summarizes, and sends the latest N emails."""
    print(f"Fetching latest {count} emails for summary report...")
    try:
        # Fetch latest N emails from inbox
        # Consider changing query if 'is:unread' is too restrictive
        raw_emails = email_fetcher.fetch_emails_since(query="in:inbox", max_results=count)

        if not raw_emails:
            print("No recent emails found matching criteria.")
            no_emails_text = f"No recent emails found (checked last {count})."
            # Optionally send 'no emails' notifications
            # ...
            return False

        print(f"Found {len(raw_emails)} emails. Processing for summaries...")
        processed_list = []
        # --- REMOVED SLEEP from loop ---
        for email in raw_emails:
            # Check if email is a dict before processing
            if not isinstance(email, dict):
                 print(f"Warning: Skipping non-dictionary item from fetcher: {type(email)}")
                 continue
            processed_email = process_single_email(email, config)
            processed_list.append(processed_email)
            # Removed time.sleep() - Now handled in llm_handler

        # --- Format the Summary Message ---
        text_report_parts = [f"** Recent Email Summary ({len(processed_list)} Emails) **\n"]
        html_report_parts = [
            "<html><head><style>body{font-family:sans-serif; line-height: 1.4;} strong{color:#333;} hr{border:none;border-top:1px solid #eee; margin: 1em 0;} p{margin: 0.5em 0;}</style></head><body>",
            f"<h2>Recent Email Summary ({len(processed_list)} Emails)</h2>"
        ]

        for i, item in enumerate(processed_list):
            # Check if item is a dictionary before accessing keys
            if not isinstance(item, dict): continue # Skip if processing failed badly

            subject = item.get('subject', 'N/S')
            sender = item.get('from', 'N/A')
            summary = item.get('summary', 'N/A')
            if summary.startswith("Error:") or summary == "Processing Error":
                 summary = f"[{summary} - Check original email]"
            date = item.get('date', '')
            category = item.get('priority_category', 'N/A')
            score = item.get('priority_score', 'N/A')

            # Text Part
            text_report_parts.append(f"--- Email {i+1} ({category.capitalize()}/{score}) ---")
            text_report_parts.append(f"Date: {date}")
            text_report_parts.append(f"From: {sender}")
            text_report_parts.append(f"Subject: {subject}")
            text_report_parts.append(f"Summary: {summary}\n")

            # HTML Part
            html_report_parts.append("<hr>")
            html_report_parts.append(f"<p><strong>From:</strong> {sender}<br>")
            html_report_parts.append(f"<strong>Subject:</strong> {subject}<br>")
            html_report_parts.append(f"<strong>Date:</strong> {date} ({category.capitalize()}/{score})<br>")
            html_report_parts.append(f"<strong>Summary:</strong> {summary}</p>")


        text_report = "\n".join(text_report_parts)
        html_report_parts.append("</body></html>")
        html_report = "".join(html_report_parts)

        # Truncate text report for WhatsApp
        max_whatsapp_len = 1600
        if len(text_report) > max_whatsapp_len:
             text_report_truncated = text_report[:max_whatsapp_len - 50]
             last_newline = text_report_truncated.rfind('\n')
             if last_newline > 0: text_report_truncated = text_report_truncated[:last_newline]
             text_report_truncated += f"\n... (truncated - showing {len(processed_list)} emails)"
        else:
             text_report_truncated = text_report

        # --- Send Notifications ---
        rules = config.get('notification_rules', {})
        whatsapp_enabled = rules.get('whatsapp_enabled', False) and notification_system.TWILIO_AVAILABLE
        email_config_present = all(k in config and config[k] for k in ['smtp_server', 'smtp_port', 'smtp_username', 'user_email']) and (config.get('smtp_password') or os.getenv('SMTP_PASSWORD'))

        # Send via WhatsApp if enabled
        if whatsapp_enabled:
             whatsapp_data = {'summary': text_report_truncated}
             print("Sending recent summary via WhatsApp...")
             notification_system.send_whatsapp_notification(whatsapp_data, config)
        else:
            print("WhatsApp notifications disabled or Twilio not available. Skipping.")

        # Send via Email if configured
        if email_config_present:
             if hasattr(notification_system, 'send_custom_email'):
                 print("Sending recent summary via Email...")
                 email_subject = f"Recent Email Summary ({len(processed_list)})"
                 notification_system.send_custom_email(email_subject, text_report, html_report, config)
             else:
                  print("Error: send_custom_email function not found in notification_system.py. Cannot send email report.")
        else:
            print("Email SMTP configuration incomplete. Skipping email report.")

        print("Recent summary report processed.")
        return True

    except Exception as e:
        print(f"Error generating or sending recent summary: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# --- Main Execution ---
def main():
    """Main function to parse arguments and start the application"""
    parser = argparse.ArgumentParser(description="LLM-Powered Email Assistant", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--recent", type=int, nargs='?', const=10, metavar="N",
                        help="Fetch, summarize, and send the latest N emails (default 10).\n"
                             "Sends a report via configured WhatsApp/Email.")
    parser.add_argument("--monitor", action="store_true", help="Run in continuous email monitoring mode (checks for NEW emails).")
    parser.add_argument("--run-digest", choices=["daily", "weekly"], help="Generate and send the specified digest email now.")
    parser.add_argument("--process-batch", type=int, metavar="N", help="Process the latest N emails once and print results to console.")
    parser.add_argument("--setup-config", action="store_true", help="Run interactive configuration setup.")
    parser.add_argument("--start-digest-service", action="store_true", help="Start the background scheduled digest service (requires 'schedule' library).")
    parser.add_argument("--test-whatsapp", action="store_true", help="Send a test WhatsApp message to the configured number.")

    args = parser.parse_args()

    if args.setup_config:
        print("Running configuration setup...")
        setup_config()
        print("Configuration setup finished. Please ensure .env file is correct.")
        return

    config = load_config()
    if os.path.exists(ENV_FILE):
         load_dotenv(dotenv_path=ENV_FILE)
         print(f"Loaded environment variables from {ENV_FILE}")
    else:
         print(f"Warning: {ENV_FILE} not found. API keys and credentials might be missing.")

    if not os.getenv("API_KEY"):
         print("CRITICAL ERROR: API_KEY environment variable not set in .env file.")
         sys.exit(1)
    else:
         print("LLM Handler Initialized.")

    mode_selected = False
    if args.recent is not None:
        mode_selected = True
        summary_count = args.recent
        print(f"--- Running Recent Summary Mode (Last {summary_count} Emails) ---")
        send_recent_summary(config, summary_count)

    elif args.monitor:
        mode_selected = True
        print("--- Starting Monitoring Mode ---")
        start_email_monitoring(config) # Blocking call
    elif args.run_digest:
        mode_selected = True
        print(f"--- Running Single {args.run_digest.capitalize()} Digest ---")
        run_single_digest(config, args.run_digest)
    elif args.process_batch:
        mode_selected = True
        print(f"--- Processing Batch of {args.process_batch} Emails ---")
        process_batch_emails(config, args.process_batch)
    elif args.start_digest_service:
        mode_selected = True
        print("--- Attempting to Start Digest Service ---")
        if start_digest_service(config):
             print("Digest service thread started. Press Ctrl+C to stop.")
             try:
                 while True: time.sleep(60)
             except KeyboardInterrupt: print("\nExiting main thread...")
        else: print("Could not start digest service.")
    elif args.test_whatsapp:
        mode_selected = True
        print("--- Running WhatsApp Test ---")
        test_whatsapp_notification(config)

    if not mode_selected:
        print("\nNo operation mode selected or specified mode finished.")
        parser.print_help(sys.stderr)
        print("\nExample Usage:")
        print("  python smart_email_assistant.py --monitor")
        print("  python smart_email_assistant.py --recent")
        print("  python smart_email_assistant.py --recent 5")
        print("  python smart_email_assistant.py --run-digest daily")
        print("  python smart_email_assistant.py --process-batch 15")
        print("  python smart_email_assistant.py --setup-config")
        print("  python smart_email_assistant.py --test-whatsapp")

if __name__ == "__main__":
    main()