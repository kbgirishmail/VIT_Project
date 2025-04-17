import os
import re
import json
from datetime import datetime
import numpy as np
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch

class EmailClassifier:
    def __init__(self, model_name="meta-llama/Llama-2-7b-chat-hf"):
        self.model_name = model_name
        
        self.urgency_keywords = [
            "urgent", "asap", "immediately", "deadline", "today", 
            "tomorrow", "emergency", "critical", "time-sensitive"
        ]
        
        self.importance_keywords = [
            "important", "priority", "critical", "essential", "significant",
            "key", "crucial", "vital", "necessary", "required"
        ]
        
        print(f"Loading model: {model_name}...")
        self.initialize_model()
        print("Model loaded successfully!")
            
    def initialize_model(self):
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Using device: {self.device}")
            
            # Use pipeline for simpler implementation
            self.pipe = pipeline(
                "text-generation",
                model=self.model_name,
                tokenizer=self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device=0 if self.device == "cuda" else -1,
                model_kwargs={"low_cpu_mem_usage": True}
            )
            
            # Set up a fallback model for low-resource environments
            self.fallback_model = "facebook/opt-125m"
            self.fallback_pipe = None  # Will be initialized only if needed
            
            self.model_loaded = True
            
        except Exception as e:
            print(f"Error initializing primary model: {e}")
            try:
                print(f"Attempting to load fallback model: {self.fallback_model}...")
                self.pipe = pipeline(
                    "text-generation",
                    model=self.fallback_model,
                    device=0 if self.device == "cuda" else -1
                )
                self.model_loaded = True
                print("Fallback model loaded successfully!")
            except Exception as e2:
                print(f"Error initializing fallback model: {e2}")
                print("Falling back to rule-based classification only")
                self.model_loaded = False
            
    def clean_text(self, text):
        if text is None:
            return ""
            
        if not isinstance(text, str):
            text = str(text)
            
        patterns = [
            r'Best regards,.*',
            r'Regards,.*',
            r'Sincerely,.*',
            r'Thanks,.*',
            r'Cheers,.*',
            r'--\s*\n.*',
            r'Sent from my .*',
            r'This email and any files.*confidential.*',
            r'CONFIDENTIALITY NOTICE:.*',
            r'<html.*?>.*?</html>',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
            
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_features(self, email_data):
        subject = email_data["subject"].lower()
        body = email_data["body"].lower()
        sender = email_data.get("sender", "").lower()
        
        urgency_count_subject = sum(1 for word in self.urgency_keywords if word in subject)
        urgency_count_body = sum(1 for word in self.urgency_keywords if word in body)
        
        importance_count_subject = sum(1 for word in self.importance_keywords if word in subject)
        importance_count_body = sum(1 for word in self.importance_keywords if word in body)
        
        email_length = len(body.split())
        
        features = {
            "urgency_count_subject": urgency_count_subject,
            "urgency_count_body": urgency_count_body / max(1, email_length / 100),
            "importance_count_subject": importance_count_subject,
            "importance_count_body": importance_count_body / max(1, email_length / 100),
            "email_length": email_length
        }
        
        return features
    
    def generate_llm_response(self, prompt, max_tokens=512):
        try:
            if not self.model_loaded:
                return None
                
            # Create different prompt formats based on model type
            if "llama" in self.model_name.lower():
                formatted_prompt = f"<s>[INST] {prompt} [/INST]"
            elif "mistral" in self.model_name.lower():
                formatted_prompt = f"<s>[INST] {prompt} [/INST]"
            else:
                formatted_prompt = f"User: {prompt}\nAssistant:"
            
            # Generate response
            outputs = self.pipe(
                formatted_prompt,
                max_new_tokens=max_tokens,
                temperature=0.3,
                do_sample=True,
                top_p=0.95,
                top_k=50,
                return_full_text=False
            )
            
            response_text = outputs[0]['generated_text']
            
            # Clean response based on model type
            if "llama" in self.model_name.lower() or "mistral" in self.model_name.lower():
                # Remove any system prompt or instruction tags
                response_text = re.sub(r'<s>|\[/INST\]|\[INST\]', '', response_text).strip()
            
            return response_text
            
        except Exception as e:
            print(f"Error in LLM generation: {e}")
            return None
    
    def classify_with_llm(self, email_data):
        try:
            prompt = f"""
            Your task is to classify an email into one of four quadrants based on urgency and importance:
            - Q1: High Urgency, High Importance - requires immediate attention
            - Q2: Low Urgency, High Importance - strategic, should be scheduled
            - Q3: High Urgency, Low Importance - quick handling or delegation
            - Q4: Low Urgency, Low Importance - can be ignored or archived
            
            Email Subject: {email_data["subject"]}
            
            Email Body: {email_data["body"][:800]}
            
            Analyze the email carefully and provide:
            1. The quadrant (Q1, Q2, Q3, or Q4)
            2. Brief reasoning for this classification
            3. Urgency score (0-10)
            4. Importance score (0-10)
            
            Format your answer EXACTLY as follows:
            QUADRANT: [Q1/Q2/Q3/Q4]
            REASONING: [Your reasoning]
            URGENCY: [Score]
            IMPORTANCE: [Score]
            """
            
            result_text = self.generate_llm_response(prompt)
            
            if result_text:
                # More robust parsing with flexible pattern matching
                quadrant_match = re.search(r'QUADRANT:\s*(Q[1-4])', result_text, re.IGNORECASE)
                reasoning_match = re.search(r'REASONING:\s*(.*?)(?=URGENCY:|$)', result_text, re.DOTALL | re.IGNORECASE)
                urgency_match = re.search(r'URGENCY:\s*(\d+)', result_text, re.IGNORECASE)
                importance_match = re.search(r'IMPORTANCE:\s*(\d+)', result_text, re.IGNORECASE)
                
                if quadrant_match:
                    quadrant = quadrant_match.group(1).upper()
                    reasoning = reasoning_match.group(1).strip() if reasoning_match else "No reasoning provided"
                    
                    try:
                        urgency = int(urgency_match.group(1)) if urgency_match else 5
                        importance = int(importance_match.group(1)) if importance_match else 5
                        
                        # Sanity check the scores
                        urgency = max(0, min(10, urgency))
                        importance = max(0, min(10, importance))
                    except ValueError:
                        # Fallback if parsing fails
                        urgency = 5
                        importance = 5
                    
                    print(f"LLM Classification result: {quadrant}, Urgency: {urgency}, Importance: {importance}")
                    return {
                        "quadrant": quadrant,
                        "reasoning": reasoning,
                        "urgency_score": urgency,
                        "importance_score": importance
                    }
                else:
                    print("LLM response did not contain the expected format, falling back to hybrid classification")
            else:
                print("No LLM response received, falling back to hybrid classification")
            
            return self.hybrid_classification(email_data)
            
        except Exception as e:
            print(f"Error in LLM classification: {e}")
            return self.hybrid_classification(email_data)
    
    def hybrid_classification(self, email_data):
        """A more robust classification that combines rule-based and heuristic approaches"""
        features = self.extract_features(email_data)
        
        # Extract more contextual signals
        subject = email_data["subject"].lower()
        body = email_data["body"].lower()
        
        # Check for additional urgency signals
        urgency_signals = [
            "by end of day" in body,
            "by tomorrow" in body,
            "by monday" in body or "by tuesday" in body or "by wednesday" in body or 
            "by thursday" in body or "by friday" in body,
            "right away" in body,
            "as soon as possible" in body,
            "asap" in body,
            "urgent" in subject,
            "need response" in body,
            "respond by" in body,
            "due date" in body
        ]
        
        # Check for additional importance signals
        importance_signals = [
            "ceo" in body or "ceo" in subject,
            "executive" in body,
            "board" in body,
            "presentation" in body,
            "meeting" in body,
            "project" in body,
            "deadline" in body,
            "client" in body,
            "customer" in body,
            "important" in subject,
            "critical" in subject
        ]
        
        # Calculate base scores from keyword counts
        urgency_score = (
            features["urgency_count_subject"] * 2 +
            features["urgency_count_body"] * 1.5
        )
        
        importance_score = (
            features["importance_count_subject"] * 2 +
            features["importance_count_body"] * 1 +
            (min(2, features["email_length"] / 300))
        )
        
        # Add additional signals
        urgency_score += sum(urgency_signals) * 1.5
        importance_score += sum(importance_signals)
        
        # Normalize scores
        urgency_score = min(10, urgency_score)
        importance_score = min(10, importance_score)
        
        # Lower thresholds to avoid excessive Q4 classification
        high_urgency = urgency_score >= 3
        high_importance = importance_score >= 3
        
        print(f"Hybrid Classification - Urgency: {urgency_score}, Importance: {importance_score}")
        
        if high_urgency and high_importance:
            quadrant = "Q1"
            reasoning = "High urgency and importance based on email content and key phrases"
        elif not high_urgency and high_importance:
            quadrant = "Q2"
            reasoning = "Important content but not time-sensitive"
        elif high_urgency and not high_importance:
            quadrant = "Q3"
            reasoning = "Time-sensitive but not strategically important"
        else:
            quadrant = "Q4"
            reasoning = "Lower priority based on content analysis"
            
        return {
            "quadrant": quadrant,
            "reasoning": reasoning,
            "urgency_score": urgency_score,
            "importance_score": importance_score
        }
    
    def summarize_email(self, email_data):
        try:
            prompt = f"""
            Summarize the following email concisely (maximum 2-3 sentences) and extract any action items:
            
            Subject: {email_data["subject"]}
            
            Body: {email_data["body"][:800]}
            
            Format your answer as:
            SUMMARY: Brief summary here
            ACTION ITEMS: 
            - Action item 1
            - Action item 2
            
            If there are no action items, simply write "No action items required."
            """
            
            result_text = self.generate_llm_response(prompt)
            
            if result_text:
                summary_match = re.search(r'SUMMARY:\s*(.*?)(?=ACTION ITEMS:|$)', result_text, re.DOTALL | re.IGNORECASE)
                action_items_section = re.search(r'ACTION ITEMS:(.*?)$', result_text, re.DOTALL | re.IGNORECASE)
                
                summary = summary_match.group(1).strip() if summary_match else "No summary available"
                
                action_items = []
                if action_items_section:
                    action_text = action_items_section.group(1)
                    items = re.findall(r'[-*\d+\.]\s+(.*?)(?=[-*\d+\.]|$)', action_text, re.DOTALL)
                    if items:
                        action_items = [item.strip() for item in items if item.strip()]
                    else:
                        # Try alternative pattern if bullet points aren't found
                        action_text_lines = action_text.strip().split('\n')
                        action_items = [line.strip() for line in action_text_lines if line.strip() and "no action" not in line.lower()]
                
                return {
                    "summary": summary,
                    "action_items": action_items
                }
            
            return {
                "summary": f"Email about: {email_data['subject']}",
                "action_items": []
            }
            
        except Exception as e:
            print(f"Error in email summarization: {e}")
            return {
                "summary": f"Email about: {email_data['subject']}",
                "action_items": []
            }
    
    def process_email(self, subject, body, sender=""):
        clean_body = self.clean_text(body)
        
        email_data = {
            "subject": subject,
            "body": clean_body,
            "sender": sender
        }
        
        classification = self.classify_with_llm(email_data)
        
        summary = self.summarize_email(email_data)
        
        return {
            "email": email_data,
            "classification": classification,
            "summary": summary
        }
    
    def format_result(self, result):
        quadrant = result["classification"]["quadrant"]
        urgency = result["classification"]["urgency_score"]
        importance = result["classification"]["importance_score"]
        
        quadrant_descriptions = {
            "Q1": "DO IMMEDIATELY (Critical)",
            "Q2": "SCHEDULE FOR LATER (Strategic)",
            "Q3": "DELEGATE OR HANDLE QUICKLY (Distraction)",
            "Q4": "DELETE OR IGNORE (Irrelevant)"
        }
        
        output = f"""
┌─────────────────────────────────────────────────────────────┐
│ EMAIL CLASSIFICATION RESULT                                 │
├─────────────────────────────────────────────────────────────┤
│ Subject: {result["email"]["subject"][:50]}{"..." if len(result["email"]["subject"]) > 50 else ""}
│                                                             │
│ QUADRANT: {quadrant} - {quadrant_descriptions[quadrant]}
│                                                             │
│ Urgency Score: {urgency:.1f}/10                             │
│ Importance Score: {importance:.1f}/10                       │
│                                                             │
│ Reasoning:                                                  │
│ {result["classification"]["reasoning"][:100]}{"..." if len(result["classification"]["reasoning"]) > 100 else ""}
│                                                             │
│ Summary:                                                    │
│ {result["summary"]["summary"][:150]}{"..." if len(result["summary"]["summary"]) > 150 else ""}
└─────────────────────────────────────────────────────────────┘
"""
        
        if result["summary"]["action_items"]:
            output += "\nAction Items:\n"
            for i, item in enumerate(result["summary"]["action_items"], 1):
                output += f"{i}. {item}\n"
        
        return output

def main():
    parser = argparse.ArgumentParser(description='Classify email based on urgency-importance matrix')
    parser.add_argument('--model', default="meta-llama/Llama-2-7b-chat-hf", 
                        help='HuggingFace model to use for classification')
    parser.add_argument('--subject', default="", help='Email subject')
    parser.add_argument('--body', default="", help='Email body')
    parser.add_argument('--input_file', help='Path to a text file containing the email')
    parser.add_argument('--test', action='store_true', help='Run with test data')
    
    args = parser.parse_args()
    
    classifier = EmailClassifier(model_name=args.model)
    
    if args.test:
        test_emails = [
            {
                "subject": "URGENT: Q1 meeting with CEO tomorrow",
                "body": "We need to prepare for the important board meeting tomorrow. This is extremely urgent and critical for our quarterly presentation. Please respond ASAP with your availability."
            },
            {
                "subject": "Strategic planning for Q3",
                "body": "We should start thinking about our strategic initiatives for Q3. This is important for our long-term goals but doesn't require immediate action."
            },
            {
                "subject": "Quick question about today's lunch menu",
                "body": "Can you tell me what's on the menu for today's lunch? Need to know ASAP as I'm heading out."
            },
            {
                "subject": "FYI: Article you might find interesting",
                "body": "I came across this article that might be of interest to you. No rush in reading it, just thought you might find it interesting when you have time."
            }
        ]
        
        print("\nTesting with sample emails...\n")
        for i, email in enumerate(test_emails, 1):
            print(f"=== Test Email {i} ===")
            result = classifier.process_email(email["subject"], email["body"])
            print(classifier.format_result(result))
            print("\n")
        return
    
    subject = args.subject
    body = args.body
    
    if args.input_file:
        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                subject_match = re.search(r'Subject:\s*(.*?)(?=Body:|$)', content, re.DOTALL)
                if subject_match:
                    subject = subject_match.group(1).strip()
                    body_match = re.search(r'Body:(.*?)$', content, re.DOTALL)
                    if body_match:
                        body = body_match.group(1).strip()
                    else:
                        body_start = content.find(subject) + len(subject)
                        body = content[body_start:].strip()
                else:
                    lines = content.split('\n', 1)
                    if len(lines) > 0:
                        subject = lines[0].strip()
                    if len(lines) > 1:
                        body = lines[1].strip()
        except Exception as e:
            print(f"Error reading input file: {e}")
    
    if not subject and not body:
        print("\nEnter email details (press Ctrl+D when finished):")
        print("Subject: ", end="")
        subject = input().strip()
        print("Body (multi-line, press Enter twice to finish):")
        body_lines = []
        line = input()
        while line.strip() != "":
            body_lines.append(line)
            line = input()
        body = "\n".join(body_lines)
    
    if subject or body:
        print("\nClassifying email...")
        result = classifier.process_email(subject, body)
        
        print(classifier.format_result(result))
    else:
        print("No email content provided. Exiting.")

if __name__ == "__main__":
    main()