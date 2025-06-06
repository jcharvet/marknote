# Plan: Improve Editor Features

This document outlines the plan to implement enhanced editor features: Find/Replace, Auto-Save, and Synchronized Scrolling.

## 1. Find/Replace Functionality

*   **Goal:** Allow users to search for text within the editor and optionally replace it.
*   **Tasks:**
    *   **UI Design:**
        *   Create a non-modal find/replace bar or a dialog.
        *   Include input fields for "Find what" and "Replace with".
        *   Add buttons: "Find Next", "Find Previous", "Replace", "Replace All".
        *   Add options: "Match case", "Whole word".
    *   **Backend Logic (in `MarkdownEditor` / `MainWindow`):**
        *   Integrate with `QsciScintilla`'s built-in find capabilities.
        *   Implement logic for "Find Next" and "Find Previous" to highlight matches and scroll to them.
        *   Implement "Replace" for the current selection/match.
        *   Implement "Replace All" to iterate through and replace all occurrences.
        *   Ensure the editor's dirty state is updated after replacements.
    *   **Integration:**
        *   Add menu items (e.g., Edit > Find, Edit > Replace) and keyboard shortcuts (Ctrl+F, Ctrl+H).

## 2. Auto-Save Functionality

*   **Goal:** Automatically save the current file at regular intervals to prevent data loss.
*   **Tasks:**
    *   **Configuration (`SettingsDialog`, `config_utils.py`):**
        *   Add a setting: "Enable Auto-Save" (checkbox).
        *   Add a setting: "Auto-Save Interval (seconds)" (spin box, e.g., default 30s or 60s).
        *   Persist these settings in `config.json`.
    *   **Core Logic (`MainWindow`):**
        *   Implement a `QTimer` that triggers based on the configured interval.
        *   On timer tick:
            *   Check if auto-save is enabled.
            *   Check if the document is dirty (compare `editor.toPlainText()` with `last_saved_text`).
            *   If both are true and `current_file` is set, call `save_file()`.
            *   If `current_file` is `None` (new, unsaved file), consider:
                *   Option 1: Disable auto-save for this file until it's manually saved once.
                *   Option 2: (More complex) Prompt the user to save the file once, then enable auto-save.
        *   Reset/restart the timer after a manual save.
        *   Provide subtle feedback (e.g., status bar message "Auto-saved at HH:MM:SS") when an auto-save occurs.

## 3. Synchronized Scrolling (Editor and Preview)

*   **Goal:** When the user scrolls in the editor, the preview pane scrolls to the corresponding position, and vice-versa.
*   **Tasks:**
    *   **Configuration (`SettingsDialog`):**
        *   Add a setting: "Enable Synchronized Scrolling" (checkbox).
    *   **Core Logic (`MainWindow`, `MarkdownEditor`, `MarkdownPreview`):**
        *   **Editor to Preview:**
            *   Connect to the editor's scroll signals (e.g., `scrollBarMoved` from `QsciScintilla`).
            *   Determine the current scroll percentage or the first visible line in the editor.
            *   Attempt to map this position to the HTML content in the `QWebEngineView`. This is the trickiest part.
                *   *Option A (Line-based - approximate):* If possible, identify HTML elements corresponding to Markdown line numbers or major structural elements (like headings). This might involve preprocessing the Markdown or injecting markers into the HTML.
                *   *Option B (Percentage-based):* Calculate the scroll percentage in the editor and apply the same percentage to the preview's scroll height using JavaScript (`window.scrollTo`).
            *   Use `QWebEngineView.page().runJavaScript()` to scroll the preview.
        *   **Preview to Editor:**
            *   This is generally harder. If implementing, listen for scroll events in the `QWebEngineView` (via JavaScript and `QWebChannel`).
            *   Try to map the visible HTML content back to a line in the editor.
        *   **Preventing Feedback Loops:**
            *   Implement a flag or mechanism to temporarily disable the synchronization in one direction when a scroll is programmatically triggered by the other.
        *   **Performance:** Ensure the synchronization logic is efficient and doesn't cause lag.

# Project Workflow & Checklist (per project rules)
- [ ] Each sub-feature (Find/Replace, Auto-Save, Synchronized Scrolling) implemented in its own branch (feature/...) with PR
- [ ] Update requirements.txt if new dependencies are added
- [ ] Update config_utils.py and config.example.json for new settings
- [ ] Update .gitignore if new files are generated
- [ ] Update README/docs for new features
- [ ] Add/Update tests for new features
- [ ] Document new settings and UI in README
- [ ] Ensure all timers/IO are async or threaded to keep UI responsive
- [ ] Run code through Black/isort before PR