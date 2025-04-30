# test_process_single_email.py
import json
from smart_email_assistant import process_single_email

# Mock config for testing
mock_config = {
    "vip_contacts": ["boss@example.com"],
    "custom_keywords": ["urgent", "deadline"],
    "notification_settings": {"push_threshold": 50, "whatsapp_threshold": 75}
}

# Mock email with attachments
mock_email = {
    "id": "test123",
    "from": "boss@example.com",
    "subject": "Urgent: Meeting Schedule",
    "content": "Please confirm your availability for the client meeting on Friday.",
    "attachments": [
        {"filename": "meeting.pdf", "data": b"%PDF-1.4 ... fake data ..."},
        {"filename": "agenda.png", "data": b"\x89PNG\r\n\x1a\n...fake image..."}
    ]
}

# Run the test
processed = process_single_email(mock_email, mock_config)

print("\n--- Processed Email Output ---")
print(json.dumps(processed, indent=4, default=str))
