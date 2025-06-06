# Feature Plan: AI - Advanced Summarization

**Objective:** Provide users with more control over the summarization process, allowing for different lengths, styles, and focus areas.

---

## 1. Define Scope of "Advanced"

*   **User-configurable Summary Length:**
    *   Options:
        *   Short (e.g., 1-2 sentences)
        *   Medium (e.g., 3-5 sentences - current default)
        *   Long (e.g., a paragraph or specific sentence count)
    *   Consider allowing a specific target sentence/word count.
*   **Summarization Style:**
    *   Options:
        *   **Paragraph:** A coherent narrative summary.
        *   **Bullet Points:** Key takeaways listed as bullet points.
*   **Focus/Keywords (Optional):**
    *   Allow users to input keywords or topics they want the summary to emphasize.
*   **Target Selection:**
    *   Summarize the entire document.
    *   Summarize currently selected text.

## 2. Backend (`ai.py`) Implementation

*   **New Method:** Create `AIMarkdownAssistant.advanced_summarize()`
    *   **Parameters:**
        *   `text_to_summarize: str`
        *   `length_preference: str` (e.g., "short", "medium", "long", or a numeric string for sentence count)
        *   `style: str` (e.g., "paragraph", "bullet_points")
        *   `keywords: Optional[list[str]]` (list of keywords to focus on)
    *   **Prompt Engineering:** Develop a new, more detailed prompt for the Gemini API that instructs it to:
        *   Adhere to the specified length.
        *   Format the output according to the chosen style.
        *   Prioritize information related to the provided keywords (if any).
        *   Maintain clarity and conciseness.
    *   **Return Value:** The generated summary string or an error message.

## 3. Frontend (`main.py` & New Dialog) Implementation

*   **New UI Element - Advanced Summarization Dialog:**
    *   Create a new dialog class (e.g., `AdvancedSummarizationDialog(QDialog)`).
    *   **Inputs:**
        *   `QComboBox` or `QRadioButtons` for "Summary Length" (Short, Medium, Long, Custom).
        *   If "Custom" length, a `QSpinBox` for sentence/word count.
        *   `QComboBox` or `QRadioButtons` for "Summary Style" (Paragraph, Bullet Points).
        *   `QLineEdit` for "Keywords (optional, comma-separated)".
        *   `QRadioButtons` for "Target" (Full Document, Selected Text - enabled/disabled based on selection in editor).
        *   OK/Cancel buttons.
    *   This dialog will gather user preferences and then call `MainWindow.trigger_advanced_summarization()`.
*   **`MainWindow` Integration:**
    *   **Menu Action:**
        *   Add a new `QAction` "Advanced Summarization..." to the "Tools" menu (or a dedicated "AI Tools" submenu).
        *   Connect this action to a method like `MainWindow.show_advanced_summarization_dialog()`.
    *   **`show_advanced_summarization_dialog()` method:**
        *   Instantiate and show the `AdvancedSummarizationDialog`.
        *   If the dialog is accepted, retrieve the settings and call `trigger_advanced_summarization()`.
    *   **`trigger_advanced_summarization()` method:**
        *   Get the text to summarize (either full document or selected text).
        *   Call `self.ai.advanced_summarize()` with the text and options from the dialog.
        *   Display the result (e.g., in `ai_results_panel`, offer to replace selection).
        *   Update status bar messages.

## 4. Error Handling and User Feedback

*   Provide clear messages for API failures or invalid user input (e.g., no text selected for "Selected Text" option).
*   Update the status bar during AI processing.

## 5. Testing
*   Test various document lengths, content types, and all combinations of summarization options.
*   Verify behavior for "Full Document" vs. "Selected Text".
*   Test edge cases (empty document, very short selection, no keywords, many keywords).