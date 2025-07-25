# email_assistant_full_ui.py
import streamlit as st
import pandas as pd
import json
import subprocess
from datetime import datetime
import sys

st.set_page_config(page_title="LLM Email Assistant Dashboard", layout="wide")
st.title("📬 LLM-Powered Email Assistant Dashboard")

PYTHON_PATH = sys.executable  # Use the current Python executable

def fetch_emails(batch_size):
    try:
        with st.spinner("Fetching emails... Please wait."):
            result = subprocess.run(
                [PYTHON_PATH, "smart_email_assistant.py", "--process-batch", str(batch_size)],
                capture_output=True,
                text=True
            )
        st.success(f"Emails fetched successfully (Batch size: {batch_size})")
        with st.expander("🔧 Script Output (stdout)"):
            st.text(result.stdout or "No output")
        with st.expander("⚠️ Script Errors (stderr)"):
            st.text(result.stderr or "No errors")
    except Exception as e:
        st.error(f"🚨 Failed to run script: {e}")


# Load processed emails from JSON
def load_processed_emails(path='processed_emails.json'):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading email data: {e}")
        return []

# Sidebar for Fetching new emails
st.sidebar.header("📥 Fetch New Emails")
batch_size = st.sidebar.number_input("Number of emails to fetch", min_value=1, max_value=50, value=5, step=1)
if st.sidebar.button("Fetch Emails"):
    print(f"Fetching {batch_size} emails...")
    fetch_emails(batch_size)
    # st.rerun()  # Reload page to reflect new emails

emails = load_processed_emails()
if not emails:
    st.warning("No emails found in processed_emails.json.")
    st.stop()

# Convert to DataFrame
df = pd.DataFrame(emails)

# Sidebar filters
st.sidebar.header("🔎 Filter Emails")
unique_categories = df['priority_category'].unique().tolist()
category_filter = st.sidebar.multiselect("Priority Category", unique_categories, default=unique_categories)

unique_senders = df['from'].unique().tolist()
sender_filter = st.sidebar.multiselect("Sender", unique_senders, default=unique_senders)

filtered = df[df['priority_category'].isin(category_filter) & df['from'].isin(sender_filter)]

# Summary Cards
st.subheader("📊 Email Priority Distribution")
priority_counts = filtered['priority_category'].value_counts()
cols = st.columns(4)
cols[0].metric("Critical", priority_counts.get("critical", 0))
cols[1].metric("High", priority_counts.get("high", 0))
cols[2].metric("Medium", priority_counts.get("medium", 0))
cols[3].metric("Low", priority_counts.get("low", 0))

# Interactive Reply & Priority UI
st.subheader("💌 Email Interaction & Reply")
for idx, email in filtered.iterrows():
    with st.expander(f"📩 {email['subject']} — [{email['priority_category'].upper()}]"):
        st.markdown(f"**From:** {email['from']}")
        st.markdown(f"**Summary:** {email['summary']}")

        reply = st.radio(
            f"💬 Suggested Reply (ID: {email['id']})",
            ["No reply"] + email.get('smart_replies', ["No suggestions."]),
            index=0,
            key=f"reply_{idx}"
        )

        priority = st.selectbox(
            "Adjust Priority:",
            ["critical", "high", "medium", "low"],
            index=["critical", "high", "medium", "low"].index(email['priority_category']),
            key=f"priority_{idx}"
        )

        if st.button(f"✅ Mark as Handled — ID: {email['id']}", key=f"handle_{idx}"):
            st.success(f"Saved reply '{reply}' and priority '{priority}'")
            log = {
                "email_id": email['id'],
                "chosen_reply": reply,
                "chosen_priority": priority,
                "timestamp": datetime.now().isoformat()
            }
            try:
                with open("user_feedback_log.json", "a") as f:
                    f.write(json.dumps(log) + "\n")
                st.balloons()
            except Exception as e:
                st.error(f"Failed to log feedback: {e}")

# Show tabular view with summary
st.subheader("📄 Filtered Email Records")
st.dataframe(filtered[['id', 'from', 'subject', 'summary', 'priority_category', 'priority_score']], use_container_width=True)