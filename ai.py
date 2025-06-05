"""
ai.py

Handles all interactions with the Gemini AI model.

This module provides the AIMarkdownAssistant class, which encapsulates the
logic for sending requests to the Gemini API and processing its responses.
It requires a Gemini API key to be configured either in `config.json`
or as an environment variable `GEMINI_API_KEY`.
"""

import os
import requests # For making HTTP requests to the Gemini API
from typing import Optional # For type hinting

from config_utils import load_app_config, CONFIG_KEY_GEMINI_API_KEY

# The URL for the specific Gemini model API endpoint
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent" # Updated to 1.5-flash

class AIMarkdownAssistant:
    """
    A class to interact with the Gemini AI for Markdown assistance.

    This assistant can perform various tasks like analyzing context,
    expanding content, analyzing a full document, refining writing,
    and processing natural language commands.
    """
    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the AIMarkdownAssistant.

        The API key is sourced in the following order:
        1. Directly provided `api_key` argument.
        2. `GEMINI_API_KEY` from `config.json`.
        3. `GEMINI_API_KEY` environment variable.

        Args:
            api_key (Optional[str], optional): The Gemini API key. Defaults to None.

        Raises:
            ValueError: If the API key cannot be found.
        """
        self.api_key = api_key
        if not self.api_key:
            # Try loading from application configuration file
            config = load_app_config()
            self.api_key = config.get(CONFIG_KEY_GEMINI_API_KEY)

        if not self.api_key: 
            # If not in config, try loading from environment variable
            self.api_key = os.environ.get("GEMINI_API_KEY")

        if not self.api_key: 
            # If API key is still not found after checking all sources
            raise ValueError(
                f"Gemini API key not set. Please add it to '{CONFIG_KEY_GEMINI_API_KEY}' "
                f"in your configuration file ({CONFIG_KEY_GEMINI_API_KEY} in config.json) "
                f"or set the GEMINI_API_KEY environment variable."
            )

    def _gemini_request(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Sends a request to the Gemini API and returns the text response.

        This private method handles the construction of the API request,
        network communication, and error handling.

        Args:
            prompt (str): The prompt to send to the AI.
            max_tokens (int, optional): The maximum number of tokens for the response.
                                        Defaults to 512.

        Returns:
            str: The AI's text response, or an error message prefixed with "[AI Error: ...]".
        """
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        # Request payload for the Gemini API
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                # Other parameters like temperature, topP can be added here
            }
        }
        try:
            # Make the POST request to the Gemini API
            # Timeout is set to 20 seconds for the request
            resp = requests.post(GEMINI_API_URL, headers=headers, params=params, json=data, timeout=20)
            
            # Raise an HTTPError for bad responses (4xx or 5xx)
            # This is a safety net if a specific HTTPError isn't caught below.
            resp.raise_for_status() 
            
            result = resp.json() # Parse the JSON response
            
            # Safely access the expected text part of the response.
            # Gemini API typically returns content in: result["candidates"][0]["content"]["parts"][0]["text"]
            try:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, TypeError):
                # Handle cases where the response structure is not as expected
                return "[AI Error: Unexpected response format from AI service.]"
        except requests.exceptions.Timeout:
            # Handle request timeout
            return "[AI Error: Request timed out. Please try again.]"
        except requests.exceptions.ConnectionError:
            # Handle connection errors (e.g., DNS failure, refused connection)
            return "[AI Error: Could not connect to AI service. Check your internet connection.]"
        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors (e.g., 400 Bad Request, 500 Internal Server Error)
            # Provides more specific feedback than the generic resp.raise_for_status()
            return f"[AI Error: AI service returned an error: {e.response.status_code} {e.response.reason}]"
        except Exception as e: 
            # Generic catch-all for any other unforeseen errors during the request
            return f"[AI Error: An unexpected error occurred: {e}]"

    def analyze_context(self, current_text: str, cursor_position: int) -> str:
        """
        Analyzes the text around the cursor and suggests Markdown formatting or continuation.

        Args:
            current_text (str): The full text in the editor.
            cursor_position (int): The current position of the cursor.

        Returns:
            str: The AI's suggestion for Markdown, or an error message.
        """
        context = self._extract_context(current_text, cursor_position)
        prompt = f"""
You are an AI assistant integrated into a Markdown editor.
The user is writing Markdown. Here is the text immediately surrounding their cursor:

---context---
{context}
---end context---

The user's cursor is conceptually at the end of this context. 
Your task is to suggest a short, relevant Markdown snippet (e.g., a list item, a formatting suggestion, a closing tag) 
that would logically follow or complete the current thought. 
Respond *only* with the suggested Markdown snippet, without any explanation or conversational text.
If the context is empty or unclear, you can suggest a common Markdown starting element like '#' or '- '.
Keep suggestions concise, ideally a few words or a single Markdown element.
Example: If context is "- List item 1\n- List item 2", a good suggestion might be "- List item 3".
Example: If context is "## Subheading", a good suggestion might be "### Sub-subheading" or a paragraph start.
"""
        # Using a smaller max_tokens for context analysis as suggestions should be short.
        return self._gemini_request(prompt, max_tokens=60)

    def expand_content(self, selected_text: str) -> str:
        """
        Expands a given piece of text (e.g., a bullet point) into a more detailed Markdown section.

        Args:
            selected_text (str): The text to expand.

        Returns:
            str: The expanded Markdown content, or an error message.
        """
        prompt = f"""
You are an AI assistant helping a user write a Markdown document.
The user has selected the following text and wants to expand it into a more detailed section:

---selected text---
{selected_text}
---end selected text---

Your task is to expand this selected text into a comprehensive Markdown section. 
This might involve adding more details, examples, explanations, or even creating sub-headings, lists, or tables if appropriate.
Ensure the output is well-formatted Markdown.
Respond *only* with the expanded Markdown content. Do not include any conversational preamble or explanation.
"""
        return self._gemini_request(prompt, max_tokens=400) # Increased max_tokens for more detailed expansion

    def analyze_document(self, full_document: str) -> str:
        """
        Analyzes a full Markdown document and provides constructive feedback.

        Args:
            full_document (str): The entire Markdown document content.

        Returns:
            str: Actionable feedback and suggestions for improvement, or an error message.
        """
        prompt = f"""
You are an AI assistant reviewing a Markdown document.
Here is the full document:

---document---
{full_document}
---end document---

Please analyze this document and provide constructive feedback. Focus on:
1.  **Structure and Organization:** Is the document logically structured? Are sections well-defined?
2.  **Heading Hierarchy:** Is the use of headings (H1, H2, H3, etc.) correct and consistent?
3.  **Content Completeness:** Are there any obvious gaps in information or areas that need more detail?
4.  **Markdown Formatting Consistency:** Is Markdown syntax used correctly and consistently (e.g., for lists, bolding, code blocks)?
5.  **Readability and Clarity:** Is the language clear and easy to understand? Are there any complex sentences that could be simplified?

Provide specific, actionable suggestions for improvement. Format your feedback clearly, perhaps using bullet points for each suggestion.
Avoid generic praise; focus on areas where the document can be improved.
"""
        return self._gemini_request(prompt, max_tokens=400) # Increased for potentially longer feedback

    def refine_writing(self, selected_text: str) -> str:
        """
        Improves a selected piece of text for clarity, conciseness, and impact,
        maintaining its original meaning.

        Args:
            selected_text (str): The text to refine.

        Returns:
            str: The refined text, or an error message.
        """
        prompt = f"""
You are an AI writing assistant.
The user has selected the following text and wants to refine it:

---text to refine---
{selected_text}
---end text to refine---

Your task is to improve this text for clarity, conciseness, and overall impact, while strictly maintaining its original meaning.
Focus on:
- Eliminating wordiness and redundancy.
- Using stronger verbs and more precise language.
- Ensuring grammatical correctness and proper sentence structure.
- Improving flow and readability.
- Using active voice where appropriate.

Respond *only* with the refined text. Do not add any explanations, apologies, or conversational phrases.
If the original text is already excellent and cannot be improved without changing its meaning, return the original text.
"""
        return self._gemini_request(prompt, max_tokens=len(selected_text) + 100) # Allow for some expansion

    def process_natural_command(self, command_text: str, selected_text: Optional[str] = None) -> str:
        """
        Processes a natural language command, optionally acting on selected text.

        This method allows users to issue commands like "summarize this", 
        "create a table from this data", etc.

        Args:
            command_text (str): The natural language command from the user.
            selected_text (Optional[str], optional): The text currently selected by the user,
                                                     if any. Defaults to None.

        Returns:
            str: The Markdown result of executing the command, or an error message.
        """
        if selected_text:
            # If there's selected text, include it in the prompt and instruct the AI
            # to consider it as the primary context for the command.
            prompt = f"""
You are an AI markdown assistant. The user has selected the following text:

---selected text---
{selected_text}
---end selected text---

They have issued the following command related to this selection (or the document in general):
"{command_text}"

Based on the command, perform the requested action.
If the command is clearly about the selected text (e.g., "summarize this", "make this a list"), apply the command to the selected text.
If the command is more general (e.g., "add a new section about X"), then the selected text might just be for context, or not relevant.
Your response should be *only* the resulting Markdown content. Do not include any conversational phrases or explanations.
For example, if asked to "make this bold", and selected text is "hello", respond with "**hello**".
If asked to "create a list of fruits", respond with "- Apple\n- Banana\n- Orange".
"""
        else:
            # If no text is selected, the command applies more generally.
            prompt = f"""
You are an AI markdown assistant. The user has issued the following command:
"{command_text}"

Based on this command, generate the appropriate Markdown content.
Your response should be *only* the resulting Markdown content. Do not include any conversational phrases or explanations.
For example, if asked to "create a list of planets", respond with "- Mercury\n- Venus\n- Earth".
"""
        return self._gemini_request(prompt, max_tokens=400) # Allow for varied command outputs

    def create_table(self, description: str) -> str:
        """
        Generates a Markdown table based on a textual description.

        Args:
            description (str): A natural language description of the table to create.
                             (e.g., "a 3-column table for products: Name, Price, Stock")

        Returns:
            str: The AI-generated Markdown table, or an error message.
        """
        prompt = f"""
You are an AI assistant helping a user create a Markdown table.

The user wants to create a table with the following description:
---description---
{description}
---end description---

Your task is to generate the Markdown code for this table. 
- Infer column headers and a reasonable number of example rows if not explicitly stated.
- Ensure the output is valid Markdown.
- Respond *only* with the Markdown table. Do not include any conversational preamble, explanation, or backticks around the markdown block.

Example if description is "a 2-column table for fruits and their colors with 2 examples":
| Fruit  | Color  |
|--------|--------|
| Apple  | Red    |
| Banana | Yellow |

Example if description is "a table with User ID, Username, and Email for 3 users":
| User ID | Username | Email                 |
|---------|----------|-----------------------|
| 1       | alice    | alice@example.com     |
| 2       | bob      | bob@example.com       |
| 3       | charlie  | charlie@example.com   |

"""
        # Using a higher max_tokens as tables can be verbose.
        return self._gemini_request(prompt, max_tokens=600)

    def analyze_table(self, table_markdown: str) -> str:
        """
        Analyzes a given Markdown table and provides insights.

        Args:
            table_markdown (str): The Markdown string of the table to analyze.

        Returns:
            str: AI-generated analysis of the table, or an error message.
        """
        prompt = f"""
You are an AI data analyst. The user has provided the following Markdown table:

---table---
{table_markdown}
---end table---

Your task is to analyze this table and provide insights. Please consider the following:
1.  **Basic Structure**: Briefly describe the table (e.g., number of rows and columns, column headers).
2.  **Data Summary**: Provide a concise summary of the data presented. What kind of information does it contain?
3.  **Potential Patterns/Trends (if any)**: Are there any obvious patterns, trends, or noteworthy data points? (e.g., highest/lowest values, common themes).
4.  **Possible Insights/Questions**: Based on the table, what are 1-2 interesting insights or questions someone might ask about this data?
5.  **Data Quality (Optional & Brief)**: If you notice any obvious inconsistencies or potential issues (e.g., mixed data types in a column that looks numeric, missing values), briefly mention them.

Format your response clearly in Markdown. Use headings or bullet points for readability.
Avoid making up data or performing complex statistical analysis unless explicitly supported by the information present.
Focus on qualitative insights based on the provided table.
If the input is not a recognizable table or is too malformed to analyze, please state that.
"""
        return self._gemini_request(prompt, max_tokens=500) # Max tokens for a reasonably detailed analysis

    def _extract_context(self, text: str, cursor_position: int, window: int = 120) -> str:
        """
        Extracts text around the cursor position to provide context.

        Args:
            text (str): The full text content.
            cursor_position (int): The current cursor position in the text.
            window (int, optional): The number of characters to extract before and
                                    after the cursor. Defaults to 120.

        Returns:
            str: The extracted contextual text.
        """
        # Ensure cursor_position is within valid bounds
        cursor_position = max(0, min(cursor_position, len(text)))
        
        start_index = max(0, cursor_position - window)
        end_index = min(len(text), cursor_position + window)
        
        return text[start_index:end_index]

    def create_mermaid_diagram(self, description: str) -> str:
        """
        Generates a Mermaid diagram code block from a natural language description.

        Args:
            description (str): A natural language description of the diagram to create.

        Returns:
            str: The AI-generated Mermaid code block (including ```mermaid ... ```), or an error message.
        """
        prompt = f"""
You are an AI assistant helping a user create a Mermaid diagram for Markdown.

The user wants to create a diagram with the following description:
---description---
{description}
---end description---

Your task is to generate the Mermaid code block for this diagram. 
- Use the correct Mermaid syntax (e.g., graph TD, flowchart, sequenceDiagram, etc.)
- Respond ONLY with the Mermaid code block, wrapped in triple backticks with 'mermaid' (e.g., ```mermaid ... ```).
- Do NOT include any explanation, preamble, or extra formatting.

Example if description is "a simple flowchart with Start, Process, End":
```mermaid
graph TD
  Start --> Process --> End
```

Example if description is "a sequence diagram for user login":
```mermaid
sequenceDiagram
  User->>Server: Login request
  Server-->>User: Auth token
```
"""
        return self._gemini_request(prompt, max_tokens=600)

    def summarize_document(self, markdown_text: str) -> str:
        """
        Summarizes a full Markdown document concisely.

        Args:
            markdown_text (str): The entire Markdown document content.

        Returns:
            str: A concise summary of the document, or an error message.
        """
        prompt = f"""
You are an expert technical writing assistant. Summarize the following Markdown document in 3-5 sentences. Focus on the main ideas, topics, and any key points. Do not include explanations, markdown formatting, or conversational phrases—just the summary text.

---document---
{markdown_text}
---end document---
"""
        return self._gemini_request(prompt, max_tokens=200)

    def auto_link_document(self, markdown_text: str, note_titles: list[str]) -> str:
        """
        Auto-link relevant terms in the markdown to other notes using markdown links.
        Args:
            markdown_text (str): The current document's markdown.
            note_titles (list[str]): List of all note titles (filenames without extension).
        Returns:
            str: The markdown with relevant terms auto-linked, or an error message.
        """
        titles_str = ', '.join(note_titles)
        prompt = f"""
You are an AI knowledge base assistant. The user is editing a markdown note. Here is the document:
---markdown---
{markdown_text}
---end markdown---

Here is a list of all other note titles in the workspace:
{titles_str}

Your task:
- For every note title, you MUST add a markdown link at the first relevant spot in the document, even if it's only a partial match or a related concept.
- Use the format [Term](NoteTitle.md).
- If you do not add at least 3 links, you have failed the task.
- Do not change the document except for adding these links.
- Return ONLY the new markdown, no explanation, no extra formatting.
- Example: If the note titles are 'Home' and 'Page Name', and the document mentions these or related concepts, link them as [Home](Home.md), [Page Name](Page Name.md) at their first occurrence.
"""
        return self._gemini_request(prompt, max_tokens=len(markdown_text) + 200)
