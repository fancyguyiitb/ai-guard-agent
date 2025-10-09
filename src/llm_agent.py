# src/llm_agent.py
import json
import re
from src.utils.config import OPENAI_API_KEY

class LLMAgent:
    """
    LLM helper for:
    - Generating security dialogue lines based on escalation level (OpenAI only)
    - Parsing identity fields from transcripts (OpenAI only)
    """
    
    def __init__(self, mode="openai"):
        # Signature kept for compatibility; this agent uses OpenAI only.
        self.openai_client = None
        self._model = "gpt-4o-mini"
        # Lazy init: clients are created on first call if API key is present
    
    def _ensure_client(self):
        if self.openai_client is None and OPENAI_API_KEY:
            try:
                try:
                    from openai import OpenAI
                    self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
                except Exception:
                    import openai
                    self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
                # print("[LLMAgent] OpenAI client initialized")
            except Exception as e:
                print(f"[LLMAgent] Failed to initialize OpenAI client: {e}")

    def generate_response(self, level: int, context: dict | None = None) -> str:
        """
        Generate a concise security message for the given escalation level (1..3).
        Returns an empty string if OpenAI is unavailable.
        """
        self._ensure_client()
        if not self.openai_client:
            return ""

        context = context or {}
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a security AI guarding a private room. "
                        "Generate firm, professional, and concise spoken lines."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Compose a short spoken line (<= 20 words) for escalation level "
                        f"{level}. Context: {json.dumps(context) if context else '{}'}"
                    ),
                },
            ]
            resp = self.openai_client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.4,
                max_tokens=60,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"[LLMAgent] OpenAI response generation error: {e}")
            return ""

    # ---- Milestone 3: Interpret user's reply ----
    def parse_identity(self, transcript: str, return_raw: bool = False):
        """
        Parse user's spoken reply to extract name, passcode, and purpose.

        Returns a dict with keys: name (str or ""), passcode (str or ""), purpose (str or "").
        Strictly uses OpenAI; if unavailable, returns empty fields.
        """
        transcript = (transcript or "").strip()
        if not transcript:
            return {"name": "", "passcode": "", "purpose": ""}

        # Ensure OpenAI client is available
        self._ensure_client()

        if not self.openai_client:
            return {"name": "", "passcode": "", "purpose": ""}

        try:
            prompt = (
                "Extract fields from the transcript.\n"
                "Fields: name, passcode, purpose.\n"
                "- passcode may be digits or words (e.g., 'orange').\n"
                "- Treat synonyms for passcode: passcode, password, code, secret, key.\n"
                "- Do not guess. If missing, use empty string.\n"
                "Return ONLY valid JSON with keys exactly: name, passcode, purpose."
                f"\n\nTranscript: {transcript}"
            )
            response = self.openai_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a precise information extraction tool. Output only JSON with keys name, passcode, purpose."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=160,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "").strip()
            json_str = content
            if json_str.startswith("```"):
                json_str = re.sub(r"^```[a-zA-Z]*", "", json_str).strip()
                if json_str.endswith("```"):
                    json_str = json_str[:-3].strip()
            data = json.loads(json_str)
            name = str(data.get("name", "")).strip()
            passcode = str(data.get("passcode", "")).strip()
            purpose = str(data.get("purpose", "")).strip()
            result = {"name": name, "passcode": passcode, "purpose": purpose}
            if return_raw:
                result["_raw"] = content
            return result
        except Exception as e:
            print(f"[LLMAgent] OpenAI parse error: {e}. Returning empty fields.")
            return {"name": "", "passcode": "", "purpose": ""} if not return_raw else {"name": "", "passcode": "", "purpose": "", "_raw": ""}

    # Heuristic parsing removed per requirements; strictly uses OpenAI.