# src/llm_agent.py
import os
from src.utils.config import OPENAI_API_KEY

class LLMAgent:
    """
    Generates responses for escalation levels using either rule-based templates
    or OpenAI API for natural language generation.
    """
    
    def __init__(self, mode="rule"):
        """
        Initialize LLM agent.
        
        Args:
            mode (str): "rule" for template-based responses or "openai" for API-based
        """
        self.mode = mode
        self.openai_client = None
        
        if mode == "openai":
            if not OPENAI_API_KEY:
                print("[LLMAgent] Warning: OPENAI_API_KEY not set, falling back to rule mode")
                self.mode = "rule"
            else:
                try:
                    import openai
                    self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    print("[LLMAgent] OpenAI client initialized")
                except ImportError:
                    print("[LLMAgent] Warning: openai package not installed, falling back to rule mode")
                    self.mode = "rule"
                except Exception as e:
                    print(f"[LLMAgent] Warning: Failed to initialize OpenAI client: {e}, falling back to rule mode")
                    self.mode = "rule"
    
    def generate_response(self, level, context=None):
        """
        Generate a response for the given escalation level.
        
        Args:
            level (int): Escalation level (1, 2, or 3)
            context (dict): Optional context about the situation
            
        Returns:
            str: Generated response text
        """
        if self.mode == "openai" and self.openai_client:
            return self._generate_openai_response(level, context)
        else:
            return self._generate_rule_response(level, context)
    
    def _generate_rule_response(self, level, context=None):
        """Generate response using predefined templates."""
        templates = {
            1: [
                "Hello, I don't recognize you. Please identify yourself.",
                "Who are you? I need to verify your identity.",
                "Unknown person detected. Please state your name and purpose."
            ],
            2: [
                "This is your second warning. Please leave immediately or identify yourself.",
                "I'm calling security. You have 30 seconds to leave.",
                "Unauthorized access detected. This is your final warning."
            ],
            3: [
                "Security breach confirmed. Alarm activated. Authorities have been notified.",
                "Intruder alert! Security is on the way. Do not move.",
                "Maximum security level reached. All systems are now locked down."
            ]
        }
        
        import random
        return random.choice(templates.get(level, templates[1]))
    
    def _generate_openai_response(self, level, context=None):
        """Generate response using OpenAI API."""
        if not self.openai_client:
            return self._generate_rule_response(level, context)
        
        prompts = {
            1: "Generate a polite but firm greeting for an unknown person detected in a secured room. Keep it under 20 words.",
            2: "Generate a stern warning for an unknown person who has not identified themselves. This is their second warning. Keep it under 20 words.",
            3: "Generate an alarm message for maximum security escalation. The person is an intruder and security is being called. Keep it under 20 words."
        }
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a security AI system. Generate short, clear security messages."},
                    {"role": "user", "content": prompts.get(level, prompts[1])}
                ],
                max_tokens=50,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[LLMAgent] OpenAI API error: {e}, falling back to rule response")
            return self._generate_rule_response(level, context)