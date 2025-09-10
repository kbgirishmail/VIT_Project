# priority_with_preferences.py
import json
import os
from priority_system import calculate_priority
from user_preferences import load_preferences

def calculate_priority_with_user_bias(email_data, config):
    """Adjust priority score based on learned user preferences."""
    # Calculate base priority
    base_score = calculate_priority(email_data, config)
    email_id = email_data.get('id')
    preferences = load_preferences()

    # Check for past interactions
    if email_id in preferences:
        actions = preferences[email_id].get('actions', [])

        # Boost if user always replies
        if actions.count("replied") >= 2:
            print(f"User has replied to {email_id} multiple times. Boosting score.")
            base_score += 10

        # Lower if mostly ignored
        if actions.count("ignored") >= 3:
            print(f"User usually ignores {email_id}. Lowering score.")
            base_score = max(0, base_score - 15)

    email_data['priority_score'] = base_score
    return base_score

# Example usage
if __name__ == "__main__":
    mock_email = {
        "id": "179abcde1234",
        "from": "client@example.com",
        "subject": "Reminder",
        "content": "Just checking in on the timeline update."  # Simplified
    }

    mock_config = {
        "vip_contacts": ["client@example.com"],
        "custom_keywords": ["urgent", "deadline"],
        "notification_settings": {"push_threshold": 50, "whatsapp_threshold": 75}
    }

    final_score = calculate_priority_with_user_bias(mock_email, mock_config)
    print(f"Final Priority Score: {final_score}")
