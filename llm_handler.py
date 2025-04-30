# llm_handler.py
import google.generativeai as genai
# We still need genai_types for GenerationConfig, even if not for FinishReason
import google.generativeai.types as genai_types
import os
import sys # Import sys for exit on critical failure
from dotenv import load_dotenv
import re # NEEDED for suggest_replies parsing and rate limit error parsing
import time # <<< ADDED: Needed for sleep

# --- Initialization ---
load_dotenv()  # Load variables from .env file

GEMINI_API_KEY = os.getenv("API_KEY")
model = None # Initialize model variable

if not GEMINI_API_KEY:
    print("Error: API_KEY environment variable not set in .env file.")
    print("LLM features will be unavailable.")
    # sys.exit("Exiting: Gemini API Key required.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = 'models/gemini-1.5-flash'
        model = genai.GenerativeModel(model_name)
        print(f"Successfully initialized Gemini model: {model_name}")
    except Exception as e:
        print(f"Error initializing Gemini model '{model_name}': {e}")
        model = None # Ensure model is None if initialization fails
    if model is None:
        print("Warning: Could not initialize any Gemini model. LLM features will return errors.")


# --- CORRECTED Helper for API Calls (v4 - Simpler Finish Reason Check + Sleep) ---
def _generate_gemini_content(prompt, function_name="LLM", max_tokens=None):
    """Helper function to call Gemini API, handle basic errors, and manage rate limits."""
    if not model:
        print(f"Error in {function_name}: LLM model not initialized.")
        return f"Error: {function_name} failed (LLM not ready)"

    if not prompt or not prompt.strip():
        print(f"Warning in {function_name}: Received empty prompt.")
        return f"Error: {function_name} failed (Empty input)"

    try:
        gen_config = None
        if max_tokens:
             try:
                  max_tokens_int = max(1, int(max_tokens))
                  gen_config = genai_types.GenerationConfig(
                      max_output_tokens=max_tokens_int
                  )
             except (ValueError, TypeError):
                  print(f"Warning in {function_name}: Invalid max_tokens value '{max_tokens}'. Using default.")

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        # === Add sleep BEFORE the API call to manage rate limits ===
        # Sleep for ~4.1 seconds to stay under 15 RPM limit (60 / 15 = 4)
        sleep_duration = 4.1
        print(f"    (Waiting {sleep_duration:.1f}s before {function_name} API call...)")
        time.sleep(sleep_duration)
        # ============================================================

        response = model.generate_content(
            prompt,
            generation_config=gen_config,
            safety_settings=safety_settings
            )

        # --- Process Response ---
        if response.prompt_feedback.block_reason:
            print(f"Warning in {function_name}: Prompt blocked - {response.prompt_feedback.block_reason}")
            return f"Error: {function_name} failed (Input blocked)"
        if not response.candidates:
             print(f"Warning in {function_name}: No candidates returned by the API.")
             return f"Error: {function_name} failed (No response)"

        # --- Check Finish Reason (More Defensive Check) ---
        finish_reason_value = None
        candidate = response.candidates[0] # Get the first candidate
        try:
            # Directly access the finish_reason attribute. Assume it might be an int or enum-like.
            raw_finish_reason = getattr(candidate, 'finish_reason', None)
            # Try to get integer value if it's enum-like, otherwise use raw value
            if hasattr(raw_finish_reason, 'value'):
                 finish_reason_value = raw_finish_reason.value
            else:
                 finish_reason_value = raw_finish_reason # Assume it might be the int directly

            finish_reason_info = f"Value {finish_reason_value}" # Log the raw value found

            # Value 1 usually means MAX_TOKENS, Value 0 usually means STOP
            # Suppress warning if we explicitly set tokens and hit the limit (value 1)
            if finish_reason_value == 1 and gen_config:
                 pass # Expected behavior
            elif finish_reason_value != 0: # Warn if not STOP (0) and not the expected MAX_TOKENS hit
                 print(f"Warning in {function_name}: Response generation finished unexpectedly - {finish_reason_info}")

        except Exception as fr_e:
             # Catch any error trying to access finish_reason
             print(f"Warning in {function_name}: Could not access or interpret finish reason: {fr_e}")


        # --- Extract Content ---
        try:
            # Check parts safely
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                # Check text safely
                if hasattr(candidate.content.parts[0], 'text'):
                     return candidate.content.parts[0].text.strip()
                else:
                    print(f"Warning in {function_name}: Response part has no text attribute.")
                    return "" # Return empty string if part exists but has no text
            else:
                # Use finish_reason_info which holds the raw value if available
                print(f"Warning in {function_name}: Response received but no content parts (Finish Reason: {finish_reason_info}).")
                return "" # Return empty string
        except (IndexError, AttributeError) as ce_e:
             print(f"Warning in {function_name}: Response structure issue accessing content parts: {ce_e}")
             return f"Error: {function_name} failed (Response Structure)"

    # --- Catch Exceptions including Rate Limit ---
    except Exception as e:
        # Check for specific 429 Rate Limit error first
        if "429" in str(e) and "quota" in str(e).lower():
             print(f"Gemini API error during {function_name}: 429 Rate Limit Exceeded.")
             match = re.search(r'retry_delay {\s*seconds: (\d+)\s*}', str(e))
             if match: print(f"  (Suggested retry delay: {match.group(1)} seconds)")
             return f"Error: {function_name} failed (Rate Limit)"
        else:
             # Handle other potential API errors
             print(f"Gemini API error during {function_name}: {str(e)}")
             return f"Error: {function_name} failed (API call error: {type(e).__name__})"


# --- Core LLM Functions (Keep existing definitions) ---
# Ensure they call the updated _generate_gemini_content helper correctly

def summarize_email(content, subject=""):
    """Generates a concise summary of the email."""
    max_len = 8000
    if len(content) > max_len:
        content = content[:max_len] + "... (truncated)"
    prompt = f"""
Summarize the key information and any action items from the following email concisely (target 1-3 sentences, max 100 words):
Subject: {subject}
Content:
{content}

Concise Summary:"""
    return _generate_gemini_content(prompt, function_name="Summarization", max_tokens=150)

def classify_email(content, subject=""):
    """Classifies the email into predefined categories."""
    categories = ["Work", "Personal", "Urgent Action", "Promotion/Newsletter", "Spam", "Other"]
    max_len = 4000
    if len(content) > max_len:
        content = content[:max_len] + "... (truncated)"
    prompt = f"""
Classify the following email into ONE of the most appropriate categories: {', '.join(categories)}.
Analyze the subject and content carefully. Prioritize 'Urgent Action' if applicable. Classify generic newsletters or marketing as 'Promotion/Newsletter'. Respond ONLY with the category name.

Subject: {subject}
Content:
{content}

Category:"""
    result = _generate_gemini_content(prompt, function_name="Classification", max_tokens=25)
    if result in categories: return result
    elif result.startswith("Error:"): return result
    elif not result:
         print(f"Warning: LLM classification returned empty string. Defaulting to 'Other'.")
         return "Other"
    else:
        print(f"Warning: LLM classification result '{result}' not in expected categories {categories}. Defaulting to 'Other'.")
        return "Other"

def detect_intent_and_sentiment(content):
    """Detects the primary intent and overall sentiment of the email."""
    intents = ["Question", "Request for Action", "Information Sharing", "Meeting/Scheduling", "Social/Chitchat", "Problem Report", "Feedback/Opinion", "Other"]
    sentiments = ["Positive", "Negative", "Neutral"]
    max_len = 4000
    if len(content) > max_len:
        content = content[:max_len] + "... (truncated)"
    prompt = f"""
Analyze the following email content. Respond ONLY with the Intent and Sentiment on separate lines, like the example.
1. Identify the primary INTENT from this list: {', '.join(intents)}.
2. Identify the overall SENTIMENT from this list: {', '.join(sentiments)}.

Content:
{content}

Intent: [Your detected intent here]
Sentiment: [Your detected sentiment here]
"""
    result = _generate_gemini_content(prompt, function_name="Intent/Sentiment", max_tokens=60)
    intent = "Other"; sentiment = "Neutral"
    if result.startswith("Error:"): return result, result
    if not result:
        print("Warning: Intent/Sentiment detection returned empty string.")
        return intent, sentiment
    try:
        lines = result.strip().split('\n')
        found_intent = False; found_sentiment = False
        for line in lines:
            line_lower = line.lower()
            if line_lower.startswith("intent"):
                detected_intent = line.split(":", 1)[1].strip() if ':' in line else line.split(maxsplit=1)[1].strip()
                if detected_intent in intents: intent = detected_intent; found_intent = True
                elif detected_intent: print(f"Warning: Detected intent '{detected_intent}' not in predefined list.")
            elif line_lower.startswith("sentiment"):
                detected_sentiment = line.split(":", 1)[1].strip() if ':' in line else line.split(maxsplit=1)[1].strip()
                if detected_sentiment in sentiments: sentiment = detected_sentiment; found_sentiment = True
                elif detected_sentiment: print(f"Warning: Detected sentiment '{detected_sentiment}' not in predefined list.")
        if not found_intent or not found_sentiment: print(f"Warning: Could not reliably parse Intent/Sentiment from response: '{result}'")
    except Exception as e:
        print(f"Error parsing intent/sentiment response: {e}. Response was: '{result}'")
        return "Other", "Neutral" # Return defaults on parsing error
    return intent, sentiment

def extract_action_items(content):
    """Extracts specific action items or tasks from the email."""
    max_len = 6000
    if len(content) > max_len:
        content = content[:max_len] + "... (truncated)"
    prompt = f"""
Carefully review the following email content. List any specific action items, tasks, requests, or deadlines mentioned.
- Focus on concrete actions required by the recipient.
- Include deadlines if specified (e.g., "by Friday EOD").
- Use bullet points (starting with '-') for each distinct item.
- If no specific action items are found, respond ONLY with the word "None".

Content:
{content}

Action Items:
- """
    result = _generate_gemini_content(prompt, function_name="Action Item Extraction", max_tokens=250)
    if result.startswith("Error:"): return [result]
    if not result or result.strip().lower() == "none": return []
    items = []; potential_items = result.strip().split('\n')
    for item in potential_items:
         cleaned_item = item.strip('-* ').strip()
         if cleaned_item: items.append(cleaned_item)
    return items

def suggest_replies(summary, max_replies=3):
    """Suggests short, relevant replies based on the email summary."""
    if not summary or summary.startswith("Error:"):
        return ["Error: Cannot suggest replies without valid summary"]
    prompt = f"""
Based ONLY on the following email summary, suggest {max_replies} very short, common, and contextually relevant potential replies (max 5-7 words each). The replies should be appropriate responses someone might actually send.
Examples: 'Okay, thanks!', 'Will look into this.', 'Sounds good.', 'Confirming receipt.', 'Let's schedule a call.', 'Got it, will update soon.'

Summary: {summary}

Suggested Replies (one per line, starting with number and period, like "1. Reply text"):
1.
2.
3.
"""
    result = _generate_gemini_content(prompt, function_name="Reply Suggestion", max_tokens=60)
    if result.startswith("Error:"): return [result]
    if not result: print("Warning: Suggest replies returned empty string."); return []
    replies = []
    try:
        lines = result.strip().split('\n')
        for line in lines:
             line = line.strip()
             match = re.match(r'^\d+[\.\)]?\s+(.*)', line)
             if match:
                 reply_text = match.group(1).strip()
                 if reply_text: replies.append(reply_text)
    except Exception as e:
        print(f"Error parsing suggested replies: {e}. Response was: '{result}'")
        return ["Error: Parsing replies failed"]
    return [r for r in replies if r][:max_replies]


# --- Example Usage (Keep as is for testing) ---
if __name__ == '__main__':
    print("Testing llm_handler functions...")
    if model is None:
         print("Cannot run tests: LLM model not initialized.")
         sys.exit(1)
    # ... (rest of test code) ...
    # Example email content for testing (Keep as is)
    test_subject = "Meeting Request & Project Update"
    test_content = """
Hi Team,

Can we schedule a brief meeting for tomorrow afternoon (April 9th) to discuss the Q2 roadmap? Please let me know your availability.

Also, quick update on Project Phoenix: The latest build passed QA, but we found a minor UI bug in the login screen. Dev team is working on it, ETA for fix is end of day today. We need to decide on the deployment strategy by Friday EOD.

Thanks,
Jane

--
Jane Doe | Project Manager
"""
    test_summary_for_replies = "Meeting requested for Apr 9 to discuss Q2 roadmap. Project Phoenix build passed QA but has minor UI bug (fix ETA today EOD), deployment decision needed by Friday EOD."

    print("\n--- Testing Summarization ---")
    summary = summarize_email(test_content, test_subject)
    print(f"Summary: {summary}")

    print("\n--- Testing Classification ---")
    classification = classify_email(test_content, test_subject)
    print(f"Classification: {classification}")

    print("\n--- Testing Intent & Sentiment ---")
    intent, sentiment = detect_intent_and_sentiment(test_content)
    print(f"Intent: {intent}, Sentiment: {sentiment}")

    print("\n--- Testing Action Item Extraction ---")
    actions = extract_action_items(test_content)
    print(f"Action Items: {actions}")

    print("\n--- Testing Reply Suggestions ---")
    replies = suggest_replies(test_summary_for_replies)
    print(f"Suggested Replies: {replies}")

    print("\n--- Testing with Short/Spammy Content ---")
    spam_subject = "!!! AMAZING OFFER JUST FOR YOU !!!"
    spam_content = "Click here now to claim your prize $$$ visit www.totally-not-a-scam.com"
    print(f"Classifying spam: {classify_email(spam_content, spam_subject)}")
    print(f"Summarizing spam: {summarize_email(spam_content, spam_subject)}")