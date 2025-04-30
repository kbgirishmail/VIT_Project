# import llm_handler

# def suggest_auto_reply(email_summary):
#     """Suggest polite, professional replies for an email summary."""
#     if not email_summary:
#         return ["No summary provided to generate reply suggestions."]

#     # Properly embed email_summary into the prompt
#     prompt = f"""
# Given this email summary:
# {email_summary}

# Draft 3 short, polite, and context-aware replies the user might send.
# Keep them under 50 words each. Output only the replies, numbered.
# """
#     response = llm_handler._generate_gemini_content(
#         prompt, function_name="Auto-Responder Suggestion", max_tokens=120
#     )

#     if not response or response.startswith("Error"):
#         return ["Could not generate suggestions: LLM error."]

#     # Process the response to extract suggestions
#     suggestions = [line.strip().lstrip("1234567890. ") for line in response.split('\n') if line.strip()]
#     return suggestions[:3]

# # Example Usage
# if __name__ == "__main__":
#     sample_summary = "The client requested the updated project timeline and mentioned a meeting on Friday afternoon to discuss further steps."
#     suggestions = suggest_auto_reply(sample_summary)
#     print("\nSuggested Auto-Replies:")
#     for reply in suggestions:
#         print(f"- {reply}")


#------------ chat-gpt
# auto_responder.py
import llm_handler

def suggest_auto_reply(email_summary):
    """Suggest up to 3 polite replies using the existing LLM handler."""
    if not email_summary:
        return ["Cannot suggest replies: summary is empty."]
    return llm_handler.suggest_replies(email_summary, max_replies=3)

# Example usage
if __name__ == "__main__":
    test_summary = "Client has asked for an updated timeline and wants a meeting this Friday."
    suggestions = suggest_auto_reply(test_summary)
    print("Suggested Auto-Replies:")
    for reply in suggestions:
        print(f"- {reply}")
