# priority_system.py
import json
import os
import re
from datetime import datetime, timedelta

def load_config():
    """Load user configuration"""
    config_path = 'config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    
    # Create default config if doesn't exist
    default_config = {
        "user_email": "",
        "vip_contacts": [],
        "custom_keywords": [],
        "notification_settings": {
            "push_threshold": 50,
            "whatsapp_threshold": 75
        }
    }
    
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=4)
    
    return default_config

def has_recent_interaction(email_address, days=7):
    """Check if there's been recent interaction with this sender"""
    # Implement logic to check for recent interactions
    # This could be based on a database of previous emails
    # Simple placeholder implementation:
    try:
        # This could be replaced with a database lookup
        recent_contacts_file = 'recent_contacts.json'
        if os.path.exists(recent_contacts_file):
            with open(recent_contacts_file, 'r') as f:
                recent_contacts = json.load(f)
                if email_address in recent_contacts:
                    last_contact = datetime.fromisoformat(recent_contacts[email_address])
                    return (datetime.now() - last_contact) <= timedelta(days=days)
    except Exception:
        pass
    return False
import re
from datetime import datetime, timedelta
import json
import os # Keep os import

# Keep load_config()

# Keep has_recent_interaction() - consider improving its storage later

def calculate_priority(email_data, config): # Pass config explicitly
    """Calculate priority score based on rules and LLM results."""
    score = 0
    # LLM Results (assuming they are added to email_data dictionary)
    classification = email_data.get('classification', 'Other')
    intent = email_data.get('intent', 'Other')
    sentiment = email_data.get('sentiment', 'Neutral')
    action_items = email_data.get('action_items', [])

    # Parse sender
    sender_email = email_data.get('from', '')
    email_match = re.search(r'<([^>]+)>', sender_email)
    sender_email = email_match.group(1).lower() if email_match else sender_email.lower()

    vip_contacts = [contact.lower() for contact in config.get('vip_contacts', [])]
    user_email_lower = config.get('user_email', '').lower()

    # --- Scoring Logic ---
    base_score = 0 # Start from 0

    # 1. Classification-based score
    if classification == "Urgent Action":
        base_score += 40
    elif classification == "Work":
        base_score += 10
    elif classification == "Personal":
         base_score += 5
    elif classification in ["Promotion/Newsletter", "Spam"]:
         base_score -= 10 # Lower priority

    # 2. Sender-based score
    is_vip = any(vip in sender_email for vip in vip_contacts)
    if is_vip:
        base_score += 40
        if sentiment == "Negative": # Negative from VIP is important
             base_score += 10

    # 3. Intent-based score
    if intent == "Request for Action":
        base_score += 15
    elif intent == "Problem Report":
         base_score += 10
    elif intent == "Meeting/Scheduling":
         base_score += 5

    # 4. Keyword-based score (use keywords from config)
    urgent_keywords = config.get('custom_keywords', []) # Use custom_keywords as urgent ones for simplicity
    subject = email_data.get('subject', '').lower()
    content = email_data.get('content', '').lower() # Use content from email_data
    if any(keyword in subject for keyword in urgent_keywords):
        base_score += 15
    elif any(keyword in content for keyword in urgent_keywords): # Check body if not in subject
         base_score += 10

    # 5. Direct addressing
    to_field = email_data.get('to', '').lower()
    if user_email_lower and user_email_lower in to_field:
         base_score += 5

    # 6. Action items presence
    if action_items:
         base_score += 5

    # 7. Recent interaction (optional boost)
    # if has_recent_interaction(sender_email):
    #     base_score += 5

    # Ensure score is not below 0
    score = max(0, base_score)
    email_data['priority_score'] = score # Add score back to dict
    return score

def categorize_emails(emails, config): # Pass config
    """Categorize emails based on score thresholds from config."""
    # Get thresholds from config or use defaults
    settings = config.get('notification_settings', {})
    # Use thresholds slightly *below* the notification triggers if needed,
    # or define explicit category thresholds. Let's use notification thresholds for simplicity.
    critical_threshold = settings.get('whatsapp_threshold', 75) # Highest alerts trigger critical
    high_threshold = settings.get('push_threshold', 50) # Next level alerts trigger high
    medium_threshold = 20 # Define a medium threshold
    low_threshold = 0

    priority_levels = {'critical': [], 'high': [], 'medium': [], 'low': []}

    for email in emails:
        # Ensure score exists, calculate if missing (should be done before)
        if 'priority_score' not in email:
             email['priority_score'] = calculate_priority(email, config)

        score = email['priority_score']
        if score >= critical_threshold:
            email['priority_category'] = 'critical'
            priority_levels['critical'].append(email)
        elif score >= high_threshold:
             email['priority_category'] = 'high'
             priority_levels['high'].append(email)
        elif score >= medium_threshold:
            email['priority_category'] = 'medium'
            priority_levels['medium'].append(email)
        else:
             email['priority_category'] = 'low'
             priority_levels['low'].append(email)

    # Sort within categories maybe? Optional.
    # for category in priority_levels:
    #     priority_levels[category].sort(key=lambda x: x['priority_score'], reverse=True)

    return priority_levels