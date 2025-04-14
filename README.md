# VIT_Project

for running:



*I. Prerequisites (Things you need *before setup):**

1.  *Python:* You need Python installed on your system. Version 3.9 or later is recommended.
2.  *Google Account:* A standard Gmail account (@gmail.com) or a Google Workspace account.
3.  *Google Cloud Project & Credentials:*
    * Go to the [Google Cloud Console](https://console.cloud.google.com/).
    * Create a new project (or use an existing one).
    * Enable the *Gmail API* for that project.
    * Create *OAuth 2.0 Credentials* for a *Desktop application*.
    * Download the credentials JSON file and save it as credentials.json in your project directory.
4.  *Google Gemini API Key:*
    * Go to [Google AI Studio](https://aistudio.google.com/) (or the Google Cloud Console under Vertex AI).
    * Generate an API key for the Gemini API.
5.  *Twilio Account & WhatsApp Setup (Optional):*
    * If you want WhatsApp notifications:
        * Create a free [Twilio account](https://www.twilio.com/try-twilio).
        * Note down your *Account SID* and *Auth Token*.
        * Set up the *Twilio Sandbox for WhatsApp* (under Messaging -> Try it out -> Send a WhatsApp message) or purchase a Twilio number capable of sending WhatsApp messages. Note down this *Twilio WhatsApp Number*.
        * Have the recipient phone number ready (*Your WhatsApp Number*).
        * The recipient *must* send the Sandbox "join" keyword to the Twilio Sandbox number to opt-in.
6.  *SMTP Password (App Password Recommended):*
    * If using Gmail SMTP (recommended), enable 2-Step Verification on the sending Google Account.
    * Generate a 16-digit *App Password* from the Google Account security settings.

*II. Setup Steps (After getting the code files):*

1.  *Place Code Files:* Ensure all the Python files (smart_email_assistant.py, llm_handler.py, email_fetcher.py, etc.) are in the same project directory.
2.  **Place credentials.json:** Make sure the credentials.json file you downloaded from Google Cloud is in that same directory.
3.  *Create Virtual Environment (Recommended):*
    * Open your terminal or command prompt in the project directory.
    * Run: python -m venv env
    * Activate it:
        * Windows: .\env\Scripts\activate
        * macOS/Linux: source env/bin/activate
4.  *Install Dependencies:*
    * Run:
        bash
        pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 google-generativeai python-dotenv beautifulsoup4 twilio pyfcm schedule requests
        
        *(Note: pyfcm for push, schedule for scheduled digests, requests might not be strictly needed now but good to have).*
5.  **Create .env File:**
    * Create a file named exactly .env in the project directory.
    * Add your secret keys and sensitive info (replace placeholders):
        dotenv
        API_KEY=YOUR_GEMINI_API_KEY_HERE
        SMTP_PASSWORD=YOUR_16_DIGIT_APP_PASSWORD_HERE # Or your actual SMTP password if not using App Password
        TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # If using WhatsApp
        TWILIO_AUTH_TOKEN=your_twilio_auth_token_here   # If using WhatsApp
        TWILIO_WHATSAPP_SENDER=+1xxxxxxxxxx             # Your Twilio sending number
        USER_WHATSAPP_RECIPIENT=+91xxxxxxxxxx           # Your receiving number
        # FCM_API_KEY=YOUR_FCM_SERVER_KEY_HERE          # If using Push
        # FCM_DEVICE_TOKENS=token1,token2               # If using Push
        
6.  **Configure config.json:**
    * Edit the config.json file.
    * *Crucially, set:* user_email, smtp_username.
    * *Remove/Verify:* Ensure sensitive keys like smtp_password, twilio_whatsapp_number, user_whatsapp_number, device_tokens are *removed* if you put them in .env.
    * *Customize:* Set vip_contacts, custom_keywords, notification thresholds/rules (whatsapp_enabled, etc.), and digest settings to your preferences.
    * Alternatively, run python smart_email_assistant.py --setup-config for an interactive setup (it might not cover all options like .env).
7.  *Initial Google Authentication:*
    * The very first time you run a command that needs to access Gmail (like --monitor or --recent), it will likely open a web browser.
    * Log in to the Google Account you want the script to read emails from (user_email usually, or whichever account credentials.json is linked to).
    * Grant the requested permissions (reading email, potentially sending/modifying if you added those scopes).
    * This will create the token.json file, storing authorization for future runs.

*III. Running the Project:*

Activate your virtual environment first (.\env\Scripts\activate or source env/bin/activate). Then use the following commands:

* *Continuous Monitoring & Notifications:*
    bash
    python smart_email_assistant.py --monitor
    
    (Press Ctrl+C to stop)

* *On-Demand Summary Report (Latest N emails):*
    bash
    python smart_email_assistant.py --recent 10
    
    (Replace 10 with the desired number, or omit for default 10)

* *Run Daily/Weekly Digest Manually:*
    bash
    python smart_email_assistant.py --run-digest daily
    python smart_email_assistant.py --run-digest weekly
    

* *Test Processing Logic (No Notifications Sent):*
    bash
    python smart_email_assistant.py --process-batch 5
    
    (Processes latest 5 emails and prints results)

* *Test WhatsApp Sending (Requires Config/.env Setup):*
    bash
    python smart_email_assistant.py --test-whatsapp
    

* **Start Scheduled Digest Service (Requires schedule library):**
    bash
    python smart_email_assistant.py --start-digest-service
    
    (Runs in background based on config.json times, press Ctrl+C to stop)

Remember to check the console output for any errors or warnings during setup and execution.