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

def calculate_priority(email):
    """Calculate priority score for an email based on various factors"""
    score = 0
    config = load_config()
    
    # Parse sender email address to handle formats like "Name <email@example.com>"
    sender_email = email['from']
    email_match = re.search(r'<([^>]+)>', sender_email)
    if email_match:
        sender_email = email_match.group(1).lower()
    else:
        sender_email = sender_email.lower()
    
    # Priority based on sender (VIP contacts)
    vip_contacts = [contact.lower() for contact in config.get('vip_contacts', [])]
    if any(vip in sender_email for vip in vip_contacts):
        score += 30
    
    # Priority based on urgency keywords in subject
    urgent_keywords = ['urgent', 'important', 'asap', 'deadline', 'critical', 'immediate']
    if 'subject' in email and any(keyword in email['subject'].lower() for keyword in urgent_keywords):
        score += 25
    
    # Priority based on user being directly addressed
    if 'to' in email and config.get('user_email', '').lower() in email['to'].lower():
        score += 15
    
    # Priority based on previous interaction patterns
    if has_recent_interaction(sender_email):
        score += 10
    
    # Priority based on custom keywords in body
    custom_keywords = config.get('custom_keywords', [])
    if 'content' in email and any(keyword in email['content'].lower() for keyword in custom_keywords):
        score += 15
    
    return score

def categorize_emails(emails):
    """Sort emails by priority score and categorize them"""
    for email in emails:
        email['priority_score'] = calculate_priority(email)
    
    # Categorize by priority level
    priority_levels = {
        'critical': [],
        'high': [],
        'medium': [],
        'low': []
    }
    
    for email in sorted(emails, key=lambda x: x['priority_score'], reverse=True):
        if email['priority_score'] >= 50:
            priority_levels['critical'].append(email)
        elif email['priority_score'] >= 30:
            priority_levels['high'].append(email)
        elif email['priority_score'] >= 15:
            priority_levels['medium'].append(email)
        else:
            priority_levels['low'].append(email)
    
    return priority_levels