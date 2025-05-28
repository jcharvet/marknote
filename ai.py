"""
ai.py - AI integration layer for Marknote

This module contains all logic for Gemini AI integration.
Set your Gemini API key as an environment variable: GEMINI_API_KEY
"""

import os
import requests

from config_utils import load_app_config, CONFIG_KEY_GEMINI_API_KEY

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

class AIMarkdownAssistant:
    def __init__(self, api_key=None):
        self.api_key = api_key
        if not self.api_key:
            config = load_app_config()
            self.api_key = config.get(CONFIG_KEY_GEMINI_API_KEY)

        if not self.api_key: # If not found in config, try environment variable
            self.api_key = os.environ.get("GEMINI_API_KEY", "")

        if not self.api_key: # If still not found, raise error
            raise ValueError(
                f"Gemini API key not set. Please add it to {CONFIG_KEY_GEMINI_API_KEY} in config.json "
                f"or set the GEMINI_API_KEY environment variable."
            )

    def _gemini_request(self, prompt, max_tokens=512):
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}
        }
        try:
            resp = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data, timeout=20)
            resp.raise_for_status()
            result = resp.json()
            # Gemini returns candidates[0]['content']['parts'][0]['text']
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"[AI Error: {e}]"

    def analyze_context(self, current_text, cursor_position):
        context = self._extract_context(current_text, cursor_position)
        prompt = f"""
I'm writing in a markdown editor. Here's my current context:

{context}

My cursor is at position [CURSOR]. 
Suggest appropriate markdown formatting or continuation.
Respond with just the suggested markdown, no explanation.
"""
        return self._gemini_request(prompt, max_tokens=60)

    def expand_content(self, selected_text):
        prompt = f"""
Expand this bullet point into a detailed markdown section:

{selected_text}

Include relevant details, examples, and formatting.
Structure the response with appropriate headings, lists, or tables.
Use proper markdown syntax.
"""
        return self._gemini_request(prompt, max_tokens=300)

    def analyze_document(self, full_document):
        prompt = f"""
Analyze this markdown document and provide constructive feedback:

{full_document}

Focus on:
1. Structure and organization
2. Heading hierarchy
3. Content completeness
4. Formatting consistency
5. Readability

Provide specific, actionable suggestions for improvement.
"""
        return self._gemini_request(prompt, max_tokens=200)

    def refine_writing(self, selected_text):
        prompt = f"""
Improve this text for clarity, conciseness, and impact:

{selected_text}

Maintain the same meaning but enhance the writing quality.
Focus on:
- Eliminating wordiness
- Using active voice
- Improving clarity
- Making language more precise

Return only the improved text without explanation.
"""
        return self._gemini_request(prompt, max_tokens=120)

    def process_natural_command(self, command_text, selected_text=None):
        """
        Process a natural language command, optionally acting on selected text.

        Args:
            command_text (str): The command to execute.
            selected_text (str, optional): The selected text to act on, if any. Defaults to None.

        Returns:
            str: The markdown result of the command.
        """
        if selected_text:
            prompt = f"""
You are an AI markdown assistant. The user has selected the following text:

---selected---
{selected_text}
---end---

They issued this command: "{command_text}"

If the command refers to the selected text (e.g., 'summarize the highlighted text'), perform the action on the selection. Otherwise, act on the whole document or as appropriate.

Return only the markdown result.
"""
        else:
            prompt = f"""
You are an AI markdown assistant. The user issued this command: "{command_text}"

Act accordingly and return only the markdown result.
"""
        return self._gemini_request(prompt, max_tokens=300)

    def _extract_context(self, text, cursor_position, window=120):
        # Extract up to 'window' chars before and after the cursor
        start = max(0, cursor_position - window)
        end = min(len(text), cursor_position + window)
        return text[start:end]
