# Marknote

A Python-based Markdown editor with AI integration (Google Gemini), built with PyQt6.

**Now supports Windows 11 and Linux (tested on Linux Mint/Ubuntu)!**

## Features
- Sidebar document library with folder tree, search, and instant file switching
- Create folders for organizing notes and documentation
- Split-screen Markdown editing and live preview
- Syntax highlighting with QScintilla
- Modern dark UI
- AI-powered suggestions, summarization, and content generation
- Efficient workflow with toolbar, context menu, and keyboard shortcuts

## Coming Soon
- Right-click context menu for files/folders (rename, delete, move)
- Drag-and-drop support for moving files and folders
- More file operations for better note management

## Getting Started
1. **Install Python 3.9+** on your system.
2. **Clone or download this repository.**
3. **Run the app:**
   - **On Windows:** Double-click `start.bat` (recommended) or run it from a terminal. This will:
     - Activate the virtual environment (if present)
     - Install/update dependencies automatically
     - Launch Marknote
   - **On Linux:** Run the `start.sh` script from a terminal:
     ```bash
     ./start.sh
     ```
     The script will check for required Qt system libraries and suggest installable packages if needed.


## How to Use Marknote for Note Taking
### Basic Editing
- Type Markdown notes in the left editor pane. The right pane shows a live preview.
- Use the toolbar for New, Open, Save, and insert Markdown links.
- Keyboard shortcuts are available for common actions.

### AI Features
#### Accessing AI
- Open the AI Command Bar:
  - Press `Ctrl+Shift+Space`, or
  - Click the AI button on the toolbar, or
  - Right-click in the editor and select "AI Command (Natural Language)" from the context menu.
- A larger, multi-line input will appear at the bottom.

#### Using AI Commands
- Type a natural language command, e.g.:
  - `Summarize the highlighted text`
  - `Expand this point into a paragraph`
  - `Refine the selected text`
  - `Analyze the document`
- Press `Ctrl+Enter` or click **Send** to submit.
- If text is selected, the AI will act on it; otherwise, it will use the full document.
- **Result:** The AI's response will always be appended to the end of your note for easy review and editing.

#### Quick AI Access
- Use the context menu or toolbar for fast access to AI features.
- All AI interactions are context-aware and designed for intuitive note-taking.

## Requirements
- Windows 11 or Linux (Mint/Ubuntu recommended)
- Python 3.9+

## AI Integration
- Uses the Gemini API for AI-powered features. No Genkit installation required—just an API key!

---

## Linux Notes
- Marknote now supports Linux! 
- On first run, the app will check for required Qt system libraries and suggest installable packages if needed.
- To start the app on Linux, use the provided `start.sh` script:
  ```bash
  ./start.sh
  ```
- If you encounter missing library errors, follow the on-screen instructions to install dependencies.

---

## Cross-Platform Support
- Marknote was originally designed for Windows but now has improved support for Linux.
- Path handling and configuration are normalized for your OS. If you find any issues or have suggestions for better cross-platform compatibility, please open an issue or pull request!

### How to Get Your Gemini API Key
1. Go to the [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account.
3. Click on "Create API key" and follow the prompts.
4. Copy your API key.
5. Paste it into `config.json` in the project root (replace `YOUR_GEMINI_API_KEY_HERE`):
   ```json
   {
     "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY_HERE"
   }
   ```
6. **Security:** Do NOT share or commit your API key publicly.

## Workflow Improvements
- `start.bat` handles venv activation and dependency installation automatically.
- All dependencies are managed via `requirements.txt`.
- See `plan.md` for technical details and future roadmap.

## Support
If you have questions or want to suggest improvements, open an issue or contribute!

## Troubleshooting (Linux: PyQt/Qt Errors)
If you encounter errors like:

```
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized.
```

This means some required system libraries for PyQt/Qt are missing on your system. To resolve this, install the following packages:

```
sudo apt-get update
sudo apt-get install libxcb-cursor0 libxcb-xinerama0 libxcb-xinput0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libgl1 libegl1 mesa-utils libxkbcommon-x11-0
```

If you see errors about missing 'venv' or 'ensurepip', also run:

```
sudo apt-get install python3-venv
```

After installing, re-run `./start.sh`.

If you are on a different Linux distribution, use your package manager to install the equivalent libraries.

## License
This project is licensed under the MIT License. See the LICENSE file for details.
