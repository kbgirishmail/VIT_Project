# test_thread_summary.py
from email_fetcher import fetch_emails_since
from smart_email_assistant import group_emails_by_thread, summarize_email_threads

# Step 1: Fetch emails
emails = fetch_emails_since(days=2)
print(f"Fetched {len(emails)} emails.")

# Step 2: Group by threadId
grouped = group_emails_by_thread(emails)
print(f"Grouped into {len(grouped)} threads.")

# Step 3: Summarize Threads
summaries = summarize_email_threads(grouped)
print("Thread Summaries:")
for thread_id, summary in summaries.items():
    print(f"\n[Thread ID: {thread_id}]\nSummary: {summary[:300]}\n---")
