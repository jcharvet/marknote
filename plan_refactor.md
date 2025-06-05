## Plan to Refactor AI Dialogs to Sidebar Panel

**Goal:** Remove disruptive AI dialog boxes and consolidate all AI interactions into the dedicated right-hand side panel (`ai_results_panel`).

This plan outlines the UX/UI considerations and the necessary code changes, primarily within `MainWindow.py`.

### I. UX/UI Considerations for the AI Panel

The existing `ai_results_panel` will be enhanced to serve as the central hub for all AI operations.

1.  **Discoverability & Initiation of Actions:**
    *   **AI Action Selector:** Introduce a `QComboBox` at the top of the AI panel to list all available AI actions (e.g., "General Command," "Summarize Page," "Create Table," etc.).
    *   **Command Input:** The existing `command_bar` (QTextEdit) will be the primary input for actions requiring text prompts. It will be disabled or ignored for actions operating on selections or the whole document.
    *   **"Send" Button:** The existing "Send" button will trigger the selected AI action.

2.  **Contextual Awareness:**
    *   The panel should implicitly understand the context: selected text, full document, or no specific context, based on the chosen action.

3.  **Displaying Prompts & Guidance:**
    *   The `command_bar`'s placeholder text should dynamically update based on the selected AI action to guide the user.
    *   The main results area can initially show brief instructions.

4.  **Displaying Results & Taking Action:**
    *   **Results Area:** Upgrade `ai_results_label` to a `QTextBrowser` (`ai_results_display`) for rich text, scrolling, and interactivity.
    *   **Action Buttons:** Dynamically add buttons below the results area relevant to the result and action type (e.g., "Insert into Document," "Replace Selection," "Copy to Clipboard," "Apply Changes").

5.  **Workflow Example (Create Table):**
    1.  User selects "Create Table" from the `QComboBox`.
    2.  `command_bar` placeholder updates to "Describe the table...".
    3.  User types description into `command_bar`.
    4.  User clicks "Send."
    5.  AI processes, results area shows "Generating table...".
    6.  Generated Markdown table appears in results area.
    7.  "Insert into Document" and "Copy to Clipboard" buttons appear.

### II. Refactoring Plan & Guidance

This involves modifying `MainWindow.py`.

**Step 1: Enhance the AI Panel UI (`MainWindow._setup_central_widget`)**

*   Rename `ai_results_label` to `ai_results_display` and change its type to `QTextBrowser`.
*   Add `ai_action_selector` (QComboBox) above the command bar.
*   Add `ai_action_buttons_area` (QWidget with QHBoxLayout) below the results display for dynamic buttons.

```python
# In _setup_central_widget
# Replace ai_results_label:
self.ai_results_display = QTextBrowser(self)
self.ai_results_display.setPlaceholderText("AI results and previews will appear here.")
self.ai_results_display.setOpenExternalLinks(False)
self.ai_results_display.anchorClicked.connect(self._handle_ai_result_link)
# ...
# ai_results_layout.addWidget(self.ai_results_label) # OLD
ai_results_layout.addWidget(self.ai_results_display) # NEW

# Add AI Action Selector:
self.ai_action_selector = QComboBox()
self.ai_action_selector.addItems([
    "General Command",
    "Summarize Page",
    "Expand Selection",
    "Refine Selection",
    "Analyze Document",
    "Analyze Selection/Table",
    "Create Table",
    "Create Mermaid Diagram",
    "Auto-Link Page",
    "Find Related Pages",
    "Semantic Search"
])
self.ai_action_selector.currentTextChanged.connect(self._on_ai_action_selected)
ai_results_layout.insertWidget(0, self.ai_action_selector) # Insert at the top

# Add dynamic buttons area:
self.ai_action_buttons_widget = QWidget()
self.ai_action_buttons_layout = QHBoxLayout()
self.ai_action_buttons_layout.setContentsMargins(0,0,0,0)
self.ai_action_buttons_widget.setLayout(self.ai_action_buttons_layout)
ai_results_layout.addWidget(self.ai_action_buttons_widget)
```

**Step 2: Create Helper Methods in `MainWindow`**

*   `_on_ai_action_selected(self, action_text: str)`: Updates placeholder, clears panel, enables/disables command bar.
*   `_clear_ai_action_buttons(self)`: Removes all buttons from the dynamic area.
*   `_add_ai_action_button(self, text: str, callback)`: Creates and adds a button.
*   `_ensure_ai_assistant(self) -> bool`: Initializes `self.ai` if needed, handles API key errors.

```python
# Add these methods to MainWindow class
def _on_ai_action_selected(self, action_text: str):
    self.command_bar.clear()
    self.ai_results_display.clear()
    self._clear_ai_action_buttons()
    # Update placeholder and enable/disable command_bar based on action_text
    if action_text == "Create Table":
        self.command_bar.setPlaceholderText("Describe the table (e.g., 3 columns: Name, Price, Stock)")
        self.command_bar.setEnabled(True)
    elif action_text == "Summarize Page":
        self.command_bar.setPlaceholderText("Click 'Send' to summarize the current page.")
        self.command_bar.setEnabled(False)
    # ... handle other actions ...
    else:
        self.command_bar.setPlaceholderText("Enter your AI command or prompt here...")
        self.command_bar.setEnabled(True)

def _clear_ai_action_buttons(self):
    while self.ai_action_buttons_layout.count():
        child = self.ai_action_buttons_layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

def _add_ai_action_button(self, text: str, callback):
    button = QPushButton(text)
    button.clicked.connect(callback)
    self.ai_action_buttons_layout.addWidget(button)

def _ensure_ai_assistant(self) -> bool:
    if self.ai:
        return True
    try:
        self.ai = AIMarkdownAssistant() # AIMarkdownAssistant handles key loading
        return True
    except ValueError as e:
        self.ai_results_display.setMarkdown(f"<b>AI Error:</b> Gemini API key not found. Please set it in Preferences via File > Preferences.<br><pre>{e}</pre>")
        self._clear_ai_action_buttons()
        return False
```

**Step 3: Modify `MainWindow.execute_command()`**

*   This method will now be triggered by the "Send" button in the AI panel.
*   It reads the selected action from `ai_action_selector` and the prompt from `command_bar`.
*   It calls the appropriate AI method based on the action type.
*   It displays results or errors in `ai_results_display`.
*   It calls `_handle_ai_response` to add action buttons.

```python
# Modify the existing execute_command method
def execute_command(self):
    if not self._ensure_ai_assistant():
        return

    action_type = self.ai_action_selector.currentText()
    prompt = self.command_bar.toPlainText().strip()
    selected_text = self.editor.selectedText()
    full_text = self.editor.toPlainText()

    self.ai_results_display.setText(f"<i>Processing '{action_type}'...</i>")
    QApplication.processEvents()

    response_text = ""
    try:
        # ... (Implement the logic to call the correct self.ai method based on action_type) ...
        # Example for General Command:
        if action_type == "General Command":
            if not prompt:
                self.ai_results_display.setText("Please enter a command.")
                return
            response_text = self.ai.process_natural_command(prompt, selected_text=selected_text or None)
        # Example for Summarize Page:
        elif action_type == "Summarize Page":
            if not full_text.strip():
                self.ai_results_display.setText("Document is empty. Nothing to summarize.")
                return
            response_text = self.ai.summarize_document(full_text)
        # ... handle other actions similarly ...
        # Special cases like Find Related Pages and Semantic Search might directly set HTML/Markdown
        # in self.ai_results_display and return early, skipping _handle_ai_response.

        if response_text.startswith("[AI Error:") or not response_text:
             self.ai_results_display.setMarkdown(f"<b>Error:</b><br><pre>{response_text or 'No response from AI.'}</pre>")
             self._clear_ai_action_buttons()
        else:
            self._handle_ai_response(response_text, action_type, original_prompt=prompt, context_text=selected_text)

    except Exception as e:
        logger.error(f"Error executing AI command '{action_type}': {e}", exc_info=True)
        self.ai_results_display.setMarkdown(f"<b>An unexpected error occurred:</b><br><pre>{e}</pre>")
        self._clear_ai_action_buttons()
```

**Step 4: Implement `MainWindow._handle_ai_response()`**

*   Displays the AI's response in `ai_results_display`.
*   Adds relevant action buttons based on the `action_type`.

```python
# Add this method to MainWindow class
def _handle_ai_response(self, response_text: str, action_type: str, original_prompt: str = None, context_text: str = None):
    self.ai_results_display.setMarkdown(response_text) # Use setMarkdown for rich text
    self._clear_ai_action_buttons()

    # Common button
    self._add_ai_action_button("Copy Result", lambda: QApplication.clipboard().setText(response_text))

    # Add action-specific buttons
    if action_type in ["General Command", "Expand Selection", "Refine Selection", "Create Table", "Create Mermaid Diagram"]:
        self._add_ai_action_button("Insert at Cursor", lambda: self.editor.insert(response_text))
        if context_text and action_type in ["General Command", "Expand Selection", "Refine Selection"]:
             self._add_ai_action_button("Replace Selection", lambda: self.editor.replaceSelectedText(response_text))

    if action_type == "Auto-Link Page":
        self._add_ai_action_button("Apply to Document", lambda: (self.editor.setPlainText(response_text), self.set_dirty(True)))

    # Add more conditions for other action types as needed
```

**Step 5: Refactor Existing AI Menu/Context Actions**

*   Modify methods like `ai_create_table`, `expand_selected_text`, etc.
*   Instead of showing dialogs or directly processing, they should now:
    1.  Call `self.show_ai_panel()`.
    2.  Set the `self.ai_action_selector.setCurrentText()` to the corresponding action.
    3.  Optionally, pre-fill `self.command_bar` or `self.ai_results_display` with context (like selected text) and instructions.
    4.  Focus the `command_bar` or the "Send" button.

```python
# Example: Modify ai_create_table
def ai_create_table(self):
    self.show_ai_panel()
    self.ai_action_selector.setCurrentText("Create Table")
    # _on_ai_action_selected will set placeholder and clear panel
    self.command_bar.setFocus()

# Example: Modify expand_selected_text (from context menu)
def expand_selected_text(self):
    if not self.editor.hasSelectedText():
        self.statusBar().showMessage("No text selected to expand.", 3000)
        self.show_ai_panel()
        self.ai_action_selector.setCurrentText("Expand Selection")
        self.ai_results_display.setText("Select text in the editor, then click 'Send'.")
        self._clear_ai_action_buttons()
        return
    self.show_ai_panel()
    self.ai_action_selector.setCurrentText("Expand Selection")
    self.ai_results_display.setText(f"Selected text:\n---\n{self.editor.selectedText()}\n---\nClick 'Send' to expand.")
    self._clear_ai_action_buttons()
    # Focus might go to Send button or stay on editor
```

**Step 6: Remove `AIPromptDialog`**

*   Delete `ai_prompt_dialog.py`.
*   Remove imports and calls to `AIPromptDialog`.

**Step 7: Remove `QMessageBox` for AI Results**

*   Remove `QMessageBox` instances used to display AI results (e.g., in `ai_summarize_page`, `ai_autolink_page`, `analyze_document`, `ai_analyze_selected_table`). Results now go to `ai_results_display`.

**Step 8: Update `show_command_bar`**

*   Modify `show_command_bar` (and its shortcut) to simply call `self.show_ai_panel()`, set the action to "General Command", and focus the `command_bar`.

```python
# Modify show_command_bar
def show_command_bar(self):
    self.show_ai_panel()
    self.ai_action_selector.setCurrentText("General Command")
    self.command_bar.setFocus()
```

**Step 9: Implement Ctrl+Enter in `command_bar`**

*   Add an event filter to the `command_bar` in `_setup_central_widget` to capture Ctrl+Enter and trigger `execute_command`.

```python
# In _setup_central_widget, after creating self.command_bar for the AI panel:
self.command_bar.installEventFilter(self)

# Add eventFilter method to MainWindow
def eventFilter(self, obj, event):
    if obj is self.command_bar and event.type() == QEvent.Type.KeyPress:
        key_event = QKeyEvent(event)
        if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and \
           key_event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.execute_command()
            return True # Event handled
    return super().eventFilter(obj, event)
```

This plan provides a structured approach to migrating the AI interactions to the dedicated sidebar panel, enhancing the user experience. Remember to test each step thoroughly as you implement it.