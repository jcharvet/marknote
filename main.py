"""
main.py

This module defines the main application window for Marknote, a Markdown editor
with AI-assisted features. It includes the primary UI components, event handling,
file operations, and integration with AI and configuration utilities.
"""
import json
import os
from pathlib import Path
import re
import sys
import textwrap
import shutil
import tempfile
import logging
import hashlib
import secrets
import datetime
import difflib

from config_utils import (
    load_app_config, save_app_config,
    CONFIG_KEY_DEFAULT_NOTES_FOLDER, CONFIG_KEY_LAST_NOTE,
    CONFIG_FILE_NAME, CONFIG_KEY_GEMINI_API_KEY, CONFIG_KEY_EDITOR_FONT_FAMILY, CONFIG_KEY_EDITOR_FONT_SIZE,
    CONFIG_KEY_PREVIEW_PANE_VISIBLE, CONFIG_KEY_SIDEBAR_VISIBLE
)

import PyQt6.QtCore # For version diagnostics
import PyQt6.QtWebEngineCore # For version diagnostics
from PyQt6.QtCore import Qt, QTimer, QEventLoop, QEvent, QPoint, QByteArray, QMimeData, QUrl, pyqtSignal, pyqtSlot, QObject # Added QByteArray, QMimeData, QUrl, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtGui import QAction, QKeySequence, QFont, QColor, QTextCharFormat, QTextCursor, QDesktopServices, QIcon, QPalette, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPushButton, QStackedWidget, QTextEdit,
    QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QDialog, QLabel, QDialogButtonBox, QListWidget, QComboBox
)
from PyQt6.Qsci import QsciLexerMarkdown, QsciScintilla
from PyQt6.QtWebEngineWidgets import QWebEngineView # QWebEngineView already imported
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage # Added for PDF preview settings
from PyQt6.QtWebChannel import QWebChannel
from PIL import Image
from langdetect import detect, LangDetectException

from ai import AIMarkdownAssistant
from settings_dialog import SettingsDialog
import markdown
from markdown.extensions.toc import TocExtension
from toc_utils import generate_anchor
import requests
from ai_prompt_dialog import AIPromptDialog
from toc_utils import extract_headings, format_toc

DEFAULT_VIEW_MODE_KEY = "default_view_mode"
REMEMBER_LAST_MODE_KEY = "remember_last_view_mode"
LAST_VIEW_MODE_KEY = "last_view_mode"

class RecentFilesManager:
    """
    Manages the list of recently opened files.

    This class handles loading, saving, and updating the list of recent files,
    persisting it to a JSON file in the user's home directory.
    """
    MAX_RECENT_FILES = 10
    RECENT_FILES_PATH = Path.home() / '.marknote_recent_files.json'

    def __init__(self):
        """Initializes RecentFilesManager, loading recent files from disk."""
        self.recent_files_list: list[str] = []
        self.load_recent_files()

    def load_recent_files(self):
        """Loads the recent files list from a JSON file."""
        if self.RECENT_FILES_PATH.exists():
            try:
                with open(self.RECENT_FILES_PATH, 'r', encoding='utf-8') as f:
                    self.recent_files_list = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                # Log or handle error, e.g., by informing the user or resetting the list
                print(f"Error loading recent files: {e}")
                self.recent_files_list = []
        else:
            self.recent_files_list = []

    def save_recent_files(self):
        """Saves the current list of recent files to a JSON file."""
        try:
            with open(self.RECENT_FILES_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.recent_files_list, f, indent=2)
        except IOError as e:
            # Log or display an error message to the user
            print(f"Error saving recent files: {e}")
            # Optionally, inform the user via QMessageBox if critical

    def add_to_recent_files(self, file_path: str):
        """
        Adds a file path to the list of recent files.

        If the path is already in the list, it's moved to the top.
        The list is capped at MAX_RECENT_FILES.

        Args:
            file_path (str): The path of the file to add.
        """
        if not file_path: # Do not add None or empty paths
            return
        
        normalized_path = str(Path(file_path).resolve()) # Ensure consistent path format

        if normalized_path in self.recent_files_list:
            self.recent_files_list.remove(normalized_path)
        self.recent_files_list.insert(0, normalized_path)
        # Keep the list at the maximum allowed size
        self.recent_files_list = self.recent_files_list[:self.MAX_RECENT_FILES]
        self.save_recent_files()

class MarkdownEditor(QsciScintilla):
    """
    A custom QsciScintilla widget tailored for Markdown editing.

    It includes syntax highlighting for Markdown, dark mode theme,
    and other editor features like auto-indent and folding.
    It also handles smart pasting of URLs.
    """
    contentChanged = pyqtSignal()  # Add signal at class level

    def __init__(self, parent=None, main_window=None):
        """
        Initializes the MarkdownEditor.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            main_window (MainWindow, optional): Reference to the main window for callbacks.
        """
        super().__init__(parent)
        self.main_window = main_window
        self._configure_editor()
        self.textChanged.connect(self._on_text_changed)

    def _configure_editor(self):
        """Sets up the editor's appearance and behavior."""
        lexer = QsciLexerMarkdown()
        lexer.setDefaultFont(QFont("Fira Mono", 12)) # Ensure lexer font is set
        # Set colors for dark mode
        lexer.setColor(QColor("#d7dae0")) # Default text
        lexer.setPaper(QColor("#282c34")) # Background

        # Configure specific Markdown elements (examples)
        # lexer.setColor(QColor("#c678dd"), QsciLexerMarkdown.Emphasis) # Italics
        # lexer.setColor(QColor("#e5c07b"), QsciLexerMarkdown.StrongEmphasis) # Bold
        # lexer.setColor(QColor("#61afef"), QsciLexerMarkdown.Link) # Links
        # lexer.setColor(QColor("#98c379"), QsciLexerMarkdown.Header1) # H1
        # lexer.setColor(QColor("#98c379"), QsciLexerMarkdown.Header2) # H2
        # lexer.setColor(QColor("#98c379"), QsciLexerMarkdown.Header3) # H3
        # lexer.setColor(QColor("#56b6c2"), QsciLexerMarkdown.BlockQuote) # Blockquotes
        # lexer.setColor(QColor("#abb2bf"), QsciLexerMarkdown.CodeBlock) # Code blocks

        self.setLexer(lexer)
        self.setUtf8(True)
        
        # Margins and Caret
        self.setMarginsBackgroundColor(QColor("#21252b"))
        self.setMarginsForegroundColor(QColor("#61AFEF")) # Line numbers color
        self.setCaretForegroundColor(QColor("#61AFEF")) # Blinking cursor color
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QColor("#2c313a")) # Background of the current line

        # Brace matching
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setMatchedBraceBackgroundColor(QColor("#3b4048"))
        self.setUnmatchedBraceForegroundColor(QColor("#ff6b6b"))

        # Indentation and Tabs
        self.setAutoIndent(True)
        self.setIndentationGuides(True)
        self.setTabWidth(4)
        self.setIndentationsUseTabs(False) # Use spaces instead of tabs

        # Folding
        self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle, margin=2)
        
        # Font for general text not covered by lexer (if any)
        self.setFont(QFont("Fira Mono", 12)) 
        
        # Ensure base styling for the widget itself
        self.setStyleSheet("background-color: #282c34; color: #d7dae0;")

    def _on_text_changed(self):
        self.contentChanged.emit()

    def toPlainText(self) -> str:
        """
        Returns the entire text content of the editor.

        Returns:
            str: The editor's current text.
        """
        return self.text()

    def setPlainText(self, text: str):
        """
        Sets the text content of the editor.

        Args:
            text (str): The text to set.
        """
        self.setText(text)

    def _process_pasted_data(self, mime_data: QMimeData) -> bool:
        print("\n*** MARKNOTE PASTE DEBUG: _process_pasted_data CALLED ***")
        if mime_data.hasText() and self.main_window:
            print(f"Processing: MimeData has text. Main window reference: {'Valid' if self.main_window else 'INVALID'}")
            text = mime_data.text().strip()
            print(f"Pasted text (stripped): '{text}'")
            
            url_match = re.match(r'^https?://\S+$', text)
            print(f"URL regex match: {url_match}")
            
            if url_match:
                print("Pasted text is a URL.")
                url = url_match.group(0)
                print(f"Detected URL: {url}")
                is_image_url = False
                image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp')

                # 1. Check by extension (quick check)
                try:
                    # Ensure URL has a path component for extension checking
                    parsed_qurl = QUrl(url)
                    # path_str will be an empty string if there's no path
                    path_str = parsed_qurl.path().lower() # Get path as string and lowercase it
                    if parsed_qurl.isValid() and path_str and path_str != "/": # Check if path exists and is not just "/"
                        if any(path_str.endswith(ext) for ext in image_extensions):
                            print(f"URL matched image extension: {path_str}")
                            is_image_url = True
                    else:
                        print(f"URL has no significant path or is invalid for extension check: {url}")
                except Exception as e:
                    print(f"Error during URL extension check: {e}")


                # 2. If not identified as image by extension, then check Content-Type via HEAD request
                if not is_image_url:
                    print("URL not identified as image by extension, proceeding to HEAD request.")
                    try:
                        response = requests.head(url, timeout=3, allow_redirects=True, stream=True)
                        response.raise_for_status()
                        content_type = response.headers.get('Content-Type', '').lower()
                        print(f"HEAD request Content-Type: {content_type}")
                        if content_type.startswith('image/'):
                            is_image_url = True
                            print("Content-Type indicates image.")
                        else:
                            print("Content-Type does NOT indicate image.")
                    except requests.RequestException as e:
                        print(f"Could not verify URL content type for {url} via HEAD request: {e}")
                    except Exception as e:
                        print(f"Unexpected error during HEAD request for {url}: {e}")
                else:
                    print("URL already identified as image by extension. Skipping HEAD request.")
                
                print(f"FINAL check, is_image_url: {is_image_url}")
                if is_image_url:
                    print("Calling handle_pasted_image_url from _process_pasted_data")
                    self.main_window.handle_pasted_image_url(url)
                    print("--- End Paste Event (_process_pasted_data handled image) ---")
                    return True # Handled
                else:
                    print("Calling handle_pasted_plain_url from _process_pasted_data")
                    self.main_window.handle_pasted_plain_url(url)
                    print("--- End Paste Event (_process_pasted_data handled plain URL) ---")
                    return True # Handled
            else: # Not a URL match
                print("Pasted text is not a URL. Fallback in _process_pasted_data.")
        else: # No text or no main_window
            if not mime_data.hasText():
                print("No text in MimeData. Fallback in _process_pasted_data.")
            if not self.main_window: # Should not happen if main_window is passed in constructor
                print("No main_window reference. Fallback in _process_pasted_data.")
        
        print("--- End Paste Event (_process_pasted_data did not handle, falling through) ---")
        return False # Not handled by this logic

    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.StandardKey.Paste):
            print("\n*** MARKNOTE PASTE DEBUG: Paste Key Detected in keyPressEvent ***")
            clipboard = QApplication.clipboard()
            if clipboard:
                mime_data = clipboard.mimeData()
                if self._process_pasted_data(mime_data): 
                    event.accept() # Indicate we've handled the event
                    print("*** MARKNOTE PASTE DEBUG: Paste event accepted in keyPressEvent. ***")
                    return # Prevent further processing of this event
            else:
                print("*** MARKNOTE PASTE DEBUG: Clipboard not available in keyPressEvent. ***")
            
            # If clipboard is None or _process_pasted_data returned False (didn't handle)
            print("*** MARKNOTE PASTE DEBUG: Paste keyPressEvent falling through to super (clipboard issue or not handled by _process_pasted_data). ***")
        
        super().keyPressEvent(event) # Call base class implementation for other keys or if paste not handled

    def insertFromMimeData(self, source: QMimeData):
        # This method might be called by context menu paste or other non-keyPressEvent actions
        print("\n*** MARKNOTE PASTE DEBUG: insertFromMimeData CALLED (e.g., by context menu) ***")
        if not self._process_pasted_data(source):
            print("Fallback to default QScintilla paste from insertFromMimeData (as _process_pasted_data returned False).")
            super().insertFromMimeData(source) # Fallback to default behavior
        else:
            print("Paste handled by _process_pasted_data via insertFromMimeData call.")
        print("--- End Paste Event (from insertFromMimeData method execution path) ---")

    def clear(self):
        """Clears all text from the editor."""
        self.setText("")                

class WikiLinkPage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_window = parent
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        url_str = url.toString()
        if url_str.startswith('wikilink://'):
            page = url_str[len('wikilink://'):].replace('%20', ' ')
            if self._main_window:
                self._main_window.handle_wiki_link(page)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)
    def createWindow(self, _type):
        return self

class WikiLinkBridge(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
    @pyqtSlot(str)
    def openWikiLink(self, page_name):
        if self.main_window is not None:
            self.main_window.handle_wiki_link(page_name)
        else:
            print("WikiLinkBridge: main_window is None! Cannot handle wiki link.")

class MarkdownPreview(QWebEngineView):
    """
    A custom QWebEngineView widget for rendering Markdown as HTML.

    It supports standard Markdown and Mermaid diagrams.
    The preview is themed for dark mode.
    """
    def __init__(self, parent=None, md_parser=None):
        """
        Initializes the MarkdownPreview.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            md_parser (markdown.Markdown, optional): The Markdown parser instance. Defaults to None.
        """
        super().__init__(parent)
        self.setStyleSheet("background-color: #21252b; color: #d7dae0; font-family: sans-serif;")
        self.current_html: str = ""
        self.base_url: QUrl = QUrl()
        self.md_parser = md_parser
        self.channel = QWebChannel(self.page())
        # Ensure bridge gets the real MainWindow
        main_window = parent if parent is not None else QApplication.activeWindow()
        self.bridge = WikiLinkBridge(main_window)
        self.channel.registerObject("wikilinkBridge", self.bridge)
        self.page().setWebChannel(self.channel)
        # Note: QWebEngineSettings.WebAttribute.PrintSupportEnabled was problematic and removed.
        # Printing is handled via QPrintDialog and page().print() in MainWindow.

    def set_markdown(self, text: str, base_url: QUrl = None):
        import re
        def mermaid_replacer(match: re.Match) -> str:
            code = match.group(1)
            return f'<div class="mermaid">{code}</div>'
        mermaid_pattern = re.compile(r'```mermaid\s*([\s\S]*?)```', re.MULTILINE)
        text_with_mermaid_divs = mermaid_pattern.sub(mermaid_replacer, text)
        def wiki_link_replacer(match: re.Match) -> str:
            page = match.group(1).strip()
            href = f"wikilink://{page.replace(' ', '%20')}"
            return f'<a href="{href}" class="wikilink">[[{page}]]</a>'
        wiki_pattern = re.compile(r'\[\[([^\]]+)\]\]')
        text_with_wikilinks = wiki_pattern.sub(wiki_link_replacer, text_with_mermaid_divs)
        if self.md_parser:
            html_body = self.md_parser.convert(text_with_wikilinks)
            self.md_parser.reset()
        else:
            html_body = markdown.markdown(text_with_wikilinks, extensions=['fenced_code', 'extra', 'md_in_html'])
        # Inject JS for wiki-link interception
        injected_js = r'''
        <script type="text/javascript" src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
        document.addEventListener("DOMContentLoaded", function() {
            if (typeof QWebChannel !== 'undefined') {
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.wikilinkBridge = channel.objects.wikilinkBridge;
                    document.querySelectorAll('a.wikilink').forEach(function(link) {
                        link.addEventListener('click', function(e) {
                            e.preventDefault();
                            var page = link.textContent.replace(/^\[\[|\]\]$/g, '').trim();
                            window.wikilinkBridge.openWikiLink(page);
                        });
                    });
                });
            }
        });
        </script>
        '''
        if '<div class="mermaid">' in html_body:
            from pathlib import Path
            mermaid_path = Path(__file__).parent / "_assets" / "mermaid.min.js"
            mermaid_url = mermaid_path.resolve().as_uri()
            full_html = f'''
            <html>
            <head>
                <style>
                    body {{ background: #fff; color: #111; font-family: sans-serif; }}
                    pre {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                    code {{ font-family: "Fira Mono", monospace; }}
                </style>
                <script src="{mermaid_url}"></script>
                {injected_js}
                <script>
                document.addEventListener("DOMContentLoaded", function() {{
                  if (window.mermaid) {{
                    mermaid.initialize({{ startOnLoad: false }});
                    mermaid.init(undefined, document.querySelectorAll('.mermaid'));
                  }}
                }});
                </script>
            </head>
            <body>{html_body}</body>
            </html>
            '''
        else:
            full_html = f'''
            <html>
            <head>
                <style>
                    body {{ background: #fff; color: #111; font-family: sans-serif; }}
                    pre {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                    code {{ font-family: "Fira Mono", monospace; }}
                </style>
                {injected_js}
            </head>
            <body>{html_body}</body>
            </html>'''
        self.current_html = full_html
        if base_url:
            self.base_url = base_url
        self.setHtml(self.current_html, baseUrl=self.base_url)

class PrintPreviewDialog(QDialog):
    """
    A dialog for showing a print preview of a PDF document.
    """
    def __init__(self, parent=None):
        """
        Initializes the PrintPreviewDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Print Preview")
        self.setMinimumSize(800, 600)
        main_layout = QVBoxLayout(self)
        self.web_view = QWebEngineView()
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self.web_view.setStyleSheet("background-color: white;")
        main_layout.addWidget(self.web_view)
        button_layout = QHBoxLayout()
        self.print_button = QPushButton("Print")
        self.print_button.clicked.connect(self.trigger_web_print)
        button_layout.addWidget(self.print_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def trigger_web_print(self):
        import tempfile, os, webbrowser
        from PyQt6.QtWidgets import QMessageBox
        
        def after_html(html_content):
            # Inject window.print() on load
            if '</body>' in html_content:
                html_content = html_content.replace('</body>', '<script>window.onload = function(){window.print();}</script></body>')
            else:
                html_content += '<script>window.onload = function(){window.print();}</script>'
            temp_dir = tempfile.gettempdir()
            html_path = os.path.join(temp_dir, "marknote_print.html")
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                webbrowser.open(f"file://{html_path}")
            except Exception as e:
                QMessageBox.critical(self, "Print Error", f"Failed to open browser for printing: {e}")
        self.web_view.page().toHtml(after_html)

    def show_preview_html(self, html_content: str, base_url: QUrl):
        if html_content:
            self.web_view.setHtml(html_content, baseUrl=base_url)
            self.print_button.setEnabled(True)
        else:
            self.web_view.setHtml("<p>Error: No HTML content to preview.</p>")
            self.print_button.setEnabled(False)

class MainWindow(QMainWindow):
    """
    The main application window for Marknote.

    This class orchestrates the UI components, including the editor, preview,
    file library, menus, and AI command bar. It handles file operations,
    AI interactions, and overall application state.
    """
    # Stylesheet for the menubar, giving it a dark theme consistent appearance
    MENUBAR_STYLESHEET = textwrap.dedent("""
        QMenuBar {
            background: #23252b;
            color: #61AFEF;
            font-size: 14px;
        }
        QMenuBar::item {
            background: transparent;
            color: #61AFEF;
            padding: 4px 12px;
        }
        QMenuBar::item:selected {
            background: #2c313a;
            color: #98c379;
        }
        QMenu {
            background: #23252b;
            color: #d7dae0;
            border: 1px solid #282c34;
        }
        QMenu::item {
            background: transparent;
            color: #d7dae0;
            padding: 6px 24px 6px 24px;
        }
        QMenu::item:selected {
            background: #2c313a;
            color: #98c379;
        }
        QMenu::separator {
            height: 1px;
            background: #282c34;
            margin: 4px 0px 4px 0px;
        }
    """)

    failed_image_downloads = set()

    def __init__(self):
        """Initializes the MainWindow, setting up UI, loading configurations, and recent files."""
        super().__init__()
        
        # Determine and set up the default folder for documents
        self.default_folder: str = self.get_or_create_default_folder()
        
        self.setWindowTitle("Marknote - Markdown Editor with AI")
        self.resize(1200, 800)  # Slightly larger default
        self.setMinimumSize(900, 600)  # Prevent too-small window
        
        # State variables
        self.current_file: str | None = None # Path to the currently open file
        self.last_saved_text: str = ""      # Content of the editor when last saved
        self.ai: AIMarkdownAssistant | None = None # AI Assistant instance

        # Initialize Markdown parser with ToC extension and custom slugify
        self.md_parser = markdown.Markdown(
            extensions=[
                'extra',
                'fenced_code',
                'nl2br',
                'md_in_html',
                TocExtension(slugify=generate_anchor, permalink=False) 
            ]
        )
        
        # Initialize UI components by calling helper methods
        self._init_menubar()
        self._init_library_panel() # Must be called before _init_editor_preview_stack if stack uses library_panel
        self._init_editor_preview_stack()
        self._init_command_bar()

        # Load and apply preview pane visibility state
        config = load_app_config()
        is_preview_visible = config.get(CONFIG_KEY_PREVIEW_PANE_VISIBLE, True) # Default to True if not found
        self.preview.setVisible(is_preview_visible)
        if hasattr(self, 'toggle_preview_action'): # Ensure action exists
            self.toggle_preview_action.setChecked(is_preview_visible)
        
        # --- Sidebar visibility ---
        sidebar_visible = config.get(CONFIG_KEY_SIDEBAR_VISIBLE, True)
        self.library_panel.setVisible(sidebar_visible)
        if hasattr(self, 'toggle_sidebar_action'):
            self.toggle_sidebar_action.setChecked(sidebar_visible)
        
        # Finalize UI setup (central widget, layout)
        self._setup_central_widget() 
        
        # Instantiate managers and load initial state
        self.recent_files_manager = RecentFilesManager()
        self.load_last_note() # Load the last opened note
        self.update_recent_files_menu() # Populate the "Open Recent" menu

        # Add Edit/Preview toggle button to the main toolbar (always visible)
        if not hasattr(self, 'toolbar'):
            self.toolbar = QToolBar("Main Toolbar")
            self.addToolBar(self.toolbar)
        self.toggle_mode_action = QAction("Edit", self)
        self.toggle_mode_action.setCheckable(False)
        self.toggle_mode_action.triggered.connect(self.toggle_mode)
        self.toolbar.addAction(self.toggle_mode_action)

        # In MainWindow.__init__, after self.toolbar and self.library_panel are initialized:
        self.toggle_sidebar_action = QAction("Toggle Sidebar", self)
        self.toggle_sidebar_action.setCheckable(True)
        self.toggle_sidebar_action.setChecked(True)
        self.toggle_sidebar_action.triggered.connect(self.toggle_sidebar)
        self.toolbar.addAction(self.toggle_sidebar_action)

        # --- Restore view mode ---
        remember_last = config.get(REMEMBER_LAST_MODE_KEY, True)
        last_mode = config.get(LAST_VIEW_MODE_KEY, None)
        default_mode = config.get(DEFAULT_VIEW_MODE_KEY, "preview")
        if remember_last and last_mode in ("preview", "edit"):
            self.set_view_mode(last_mode)
        else:
            self.set_view_mode(default_mode)

    def set_view_mode(self, mode):
        if mode == 'edit':
            self.stack.setCurrentIndex(1)
            self.toggle_mode_action.setText("Preview")
            self.current_mode = 'edit'
        else:
            self.update_preview()
            self.stack.setCurrentIndex(0)
            self.toggle_mode_action.setText("Edit")
            self.current_mode = 'preview'

    def _toggle_preview_pane(self):
        """Toggles the visibility of the HTML preview pane and saves the state."""
        is_visible = not self.preview.isVisible()
        self.preview.setVisible(is_visible)
        self.toggle_preview_action.setChecked(is_visible)
        
        config = load_app_config()
        config[CONFIG_KEY_PREVIEW_PANE_VISIBLE] = is_visible
        save_app_config(config)

    def print_document(self):
        """Show HTML preview dialog and let user print via browser's print dialog."""
        if not self.preview:
            QMessageBox.critical(self, "Error", "Preview pane is not available.")
            return
        html_content = self.preview.current_html
        base_url = self.preview.base_url
        if not html_content:
            QMessageBox.warning(self, "Print Error", "No content to preview or print.")
            return
        preview_dialog = PrintPreviewDialog(self)
        preview_dialog.show_preview_html(html_content, base_url)
        preview_dialog.exec()

    def _handle_print_finished(self, success: bool):
        """
        Callback for when the print operation is finished.

        Args:
            success (bool): True if printing was successful, False otherwise.
        """
        if success:
            print("Print operation successful.")
            # Optionally, inform the user with a QMessageBox
            # QMessageBox.information(self, "Print Status", "Document printed successfully.")
        else:
            print("Print operation failed.")
            QMessageBox.warning(self, "Print Error", "Could not print the document.")
        
    def command_bar_key_press_event(self, event: QEvent): # Added type hint for event
        """
        Handles key press events for the AI command bar.
        Specifically, Ctrl+Enter executes the command.

        Args:
            event (QEvent): The key event.
        """
        from PyQt6.QtGui import QKeyEvent # Local import for type checking if needed
        if isinstance(event, QKeyEvent): # Ensure it's a QKeyEvent
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier and \
               event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.execute_command()
            else:
                # Default handling for other key presses in the QTextEdit
                QTextEdit.keyPressEvent(self.command_bar, event) 
        else:
            # Fallback for other event types, though primarily expecting QKeyEvent
            QTextEdit.keyPressEvent(self.command_bar, event)


    def closeEvent(self, event: QEvent): # Added type hint for event
        """
        Handles the window close event.

        Prompts the user to save unsaved changes and saves the last note/recent files.

        Args:
            event (QEvent): The close event.
        """
        if not self.maybe_save_changes():
            event.ignore() # Abort closing if user cancels or save fails
        else:
            # Save the path of the current file as the last opened note
            if self.current_file and self.current_file.endswith('.md'):
                self.save_last_note(self.current_file)
            # Add current file to recent files list (manager handles duplicates)
            if self.current_file: # Ensure current_file is not None
                self.recent_files_manager.add_to_recent_files(self.current_file)
            event.accept() # Proceed with closing

    def _init_menubar(self):
        """Initializes the main menubar and its menus (File, View, Tools, Help)."""
        menubar = self.menuBar()
        menubar.setStyleSheet(self.MENUBAR_STYLESHEET)

        # --- File Menu ---
        file_menu = menubar.addMenu("File")

        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)

        open_file_action = QAction("Open File", self)
        open_file_action.triggered.connect(self.open_file)
        file_menu.addAction(open_file_action)

        open_folder_action = QAction("Open Folder", self)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        self.recent_files_menu = QMenu("Open Recent", self)
        file_menu.addMenu(self.recent_files_menu)
        # update_recent_files_menu is called during __init__ after manager is ready

        file_menu.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        self.print_action = QAction(QIcon.fromTheme("document-print"), "&Print...", self)
        self.print_action.setShortcut(QKeySequence.StandardKey.Print)
        self.print_action.triggered.connect(self.print_document)
        file_menu.addAction(self.print_action)

        file_menu.addSeparator()

        preferences_action = QAction("Preferences...", self)
        preferences_action.setShortcut(QKeySequence("Ctrl+,"))
        preferences_action.triggered.connect(self._open_settings_dialog)
        file_menu.addAction(preferences_action)

        file_menu.addSeparator()

        export_as_action = QAction("Export As...", self)
        export_as_action.triggered.connect(self.export_file_as)
        file_menu.addAction(export_as_action)
        
        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close_application)
        file_menu.addAction(exit_action)

        # --- View Menu ---
        view_menu = menubar.addMenu("&View")
        self.toggle_preview_action = QAction("Toggle Preview Pane", self, checkable=True)
        self.toggle_preview_action.triggered.connect(self._toggle_preview_pane)
        view_menu.addAction(self.toggle_preview_action)

        # --- Tools Menu ---
        self.tools_menu = menubar.addMenu("Tools")
        
        link_action = QAction("Insert Link", self)
        link_action.triggered.connect(self.insert_link)
        self.tools_menu.addAction(link_action)

        insert_image_action = QAction("Insert Image...", self)
        insert_image_action.triggered.connect(self.insert_image)
        self.tools_menu.addAction(insert_image_action)
        
        self.tools_menu.addSeparator()

        # --- AI Actions (flat, grouped) ---
        ai_command_action = QAction("AI Command", self)
        ai_command_action.setShortcut(QKeySequence("Ctrl+Shift+Space"))
        ai_command_action.triggered.connect(lambda: self.ai_prompt_action('command'))
        self.tools_menu.addAction(ai_command_action)

        ai_create_table_action = QAction("AI Create Table...", self)
        ai_create_table_action.triggered.connect(self.ai_create_table)
        self.tools_menu.addAction(ai_create_table_action)

        ai_create_mermaid_action = QAction("AI Create Mermaid Diagram...", self)
        ai_create_mermaid_action.triggered.connect(self.ai_create_mermaid_diagram)
        self.tools_menu.addAction(ai_create_mermaid_action)

        ai_summary_action = QAction("Summarize Page", self)
        ai_summary_action.triggered.connect(self.ai_summarize_page)
        self.tools_menu.addAction(ai_summary_action)

        ai_autolink_action = QAction("Auto-Link Page", self)
        ai_autolink_action.triggered.connect(self.ai_autolink_page)
        self.tools_menu.addAction(ai_autolink_action)

        ai_related_action = QAction("Find Related Pages", self)
        ai_related_action.triggered.connect(self.ai_find_related_pages)
        self.tools_menu.addAction(ai_related_action)

        ai_semantic_search_action = QAction("Semantic Search", self)
        ai_semantic_search_action.triggered.connect(self.ai_semantic_search)
        self.tools_menu.addAction(ai_semantic_search_action)

        self.tools_menu.addSeparator()

        toc_action = QAction("Generate Table of Contents", self)
        toc_action.triggered.connect(self.insert_table_of_contents)
        self.tools_menu.addAction(toc_action)

        # --- Help Menu ---
        help_menu = menubar.addMenu("Help")
        syntax_action = QAction("Markdown & Mermaid Syntax", self)
        syntax_action.triggered.connect(self.show_syntax_help)
        help_menu.addAction(syntax_action)

    def init_ui(self):
        # Set dark palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#282c34"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#d7dae0"))
        self.setPalette(palette)

        # Menu bar with File and Help
        menubar = self.menuBar()
        menubar.setStyleSheet(self.MENUBAR_STYLESHEET)

        # File Menu
        file_menu = menubar.addMenu("File")

        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)

        open_file_action = QAction("Open File", self)
        open_file_action.triggered.connect(self.open_file)
        file_menu.addAction(open_file_action)

        open_folder_action = QAction("Open Folder", self)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        # Open Recent submenu (placeholder for now)
        self.recent_files_menu = QMenu("Open Recent", self)
        file_menu.addMenu(self.recent_files_menu)
        self.update_recent_files_menu() # Call to populate it (will be empty initially)

        file_menu.addSeparator()

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As", self)
        save_as_action.triggered.connect(self.save_file_as)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        print_action = QAction("Print", self)
        print_action.triggered.connect(self.print_document)
        print_action.setShortcut(QKeySequence("Ctrl+P"))
        file_menu.addAction(print_action)

        file_menu.addSeparator()

        export_as_action = QAction("Export As...", self)
        export_as_action.triggered.connect(self.export_file_as)
        file_menu.addAction(export_as_action)

        insert_image_action = QAction("Insert Image...", self)
        insert_image_action.triggered.connect(self.insert_image)
        file_menu.addAction(insert_image_action)

        file_menu.addSeparator() # Added separator for consistency

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close_application)
        file_menu.addAction(exit_action)

        # --- Other Menu ---
        other_menu = menubar.addMenu("Other")

        link_action = QAction("Insert Link", self) # More descriptive
        link_action.triggered.connect(self.insert_link)
        other_menu.addAction(link_action)

        ai_command_action = QAction("AI Command", self) # More descriptive
        ai_command_action.setShortcut(QKeySequence("Ctrl+Shift+Space"))
        ai_command_action.triggered.connect(lambda: self.ai_prompt_action('command'))
        other_menu.addAction(ai_command_action)
        
        # --- Help Menu ---
        help_menu = menubar.addMenu("Help")
        syntax_action = QAction("Markdown & Mermaid Syntax", self)
        syntax_action.triggered.connect(self.show_syntax_help)
        help_menu.addAction(syntax_action)

        # Remove 'Other' menu, only add 'Tools' menu
        tools_menu = self.menuBar().addMenu("Tools")
        link_action = QAction("Insert Link", self)
        link_action.triggered.connect(self.insert_link)
        tools_menu.addAction(link_action)
        ai_command_action = QAction("AI Command", self)
        ai_command_action.setShortcut(QKeySequence("Ctrl+Shift+Space"))
        ai_command_action.triggered.connect(lambda: self.ai_prompt_action('command'))
        tools_menu.addAction(ai_command_action)
        insert_image_action = QAction("Insert Image...", self)
        insert_image_action.triggered.connect(self.insert_image)
        tools_menu.addAction(insert_image_action)
        ai_create_table_action = QAction("AI Create Table...", self)
        ai_create_table_action.triggered.connect(self.ai_create_table)
        tools_menu.addAction(ai_create_table_action)
        ai_create_mermaid_action = QAction("AI Create Mermaid Diagram...", self)
        ai_create_mermaid_action.triggered.connect(self.ai_create_mermaid_diagram)
        tools_menu.addAction(ai_create_mermaid_action)
        toc_action = QAction("Generate Table of Contents", self)
        toc_action.triggered.connect(self.insert_table_of_contents)
        tools_menu.addAction(toc_action)

    def _setup_central_widget(self):
        central_widget = QWidget()
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

        # Add the library panel and the stack (preview/editor)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.library_panel)
        main_layout.addWidget(self.stack, 1)
        main_container = QWidget()
        main_container.setLayout(main_layout)
        central_layout.addWidget(main_container)

        # The AI command bar is added below the main area
        central_layout.addWidget(self.command_bar_widget)

        # Footer toolbar for language display
        self.footer_toolbar = QToolBar("Footer Toolbar")
        self.footer_toolbar.setMovable(False)
        self.footer_toolbar.setStyleSheet("background: #23252b; color: #61AFEF; border-top: 1px solid #4b5263;")
        self.language_label = QLabel("Language: ...")
        self.footer_toolbar.addWidget(self.language_label)
        self.language_override_combo = QComboBox()
        self.language_override_combo.setEditable(True)
        self.language_override_combo.setFixedWidth(120)
        self.language_override_combo.addItem("")
        self.language_override_combo.addItems([
            "English", "French", "German", "Spanish", "Italian", "Portuguese", "Dutch", "Russian", "Chinese", "Japanese", "Korean"
        ])
        self.language_override_combo.setToolTip("Override detected language")
        self.language_override_combo.currentTextChanged.connect(self.set_language_override)
        self.footer_toolbar.addWidget(self.language_override_combo)
        central_layout.addWidget(self.footer_toolbar)
        self.update_language_label()

    def _init_library_panel(self):
        """Initializes the document library panel on the left side of the window."""
        self.library_panel = QWidget() 
        library_layout = QVBoxLayout()
        library_layout.setContentsMargins(0, 0, 0, 0) 
        self.library_panel.setLayout(library_layout)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search documents...")
        self.search_bar.textChanged.connect(self.filter_library)
        library_layout.addWidget(self.search_bar)

        self.folder_btn = QPushButton("New Folder")
        self.folder_btn.clicked.connect(self.create_folder)
        self.folder_btn.setStyleSheet("background: #282c34; color: #98c379; border: none; padding: 5px;")
        library_layout.addWidget(self.folder_btn)

        self.library = QTreeWidget()
        self.library.setHeaderHidden(True) 
        self.library.setStyleSheet("background: #23252b; color: #61AFEF; font-size: 13px; border: none;")
        self.library.setMaximumWidth(210) 
        self.library.itemClicked.connect(self.open_tree_item)
        self.library.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library.customContextMenuRequested.connect(self.show_library_context_menu)
        library_layout.addWidget(self.library)
        
        self.refresh_library()

    def _init_editor_preview_stack(self):
        """Initializes the Markdown editor and preview, managed by a QStackedWidget."""
        self.editor = MarkdownEditor(parent=self, main_window=self)
        self.preview = MarkdownPreview(parent=self, md_parser=self.md_parser)
        self.editor.contentChanged.connect(self._on_editor_content_changed)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.preview)  # index 0: Preview (default)
        self.stack.addWidget(self.editor)   # index 1: Editor
        self.current_mode = 'preview'  # or 'edit'

        self.ai = AIMarkdownAssistant()  # Initialize AI assistant
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)

    def _init_command_bar(self):
        """Initializes the AI command bar at the bottom of the window."""
        self.command_bar_widget = QWidget(self) # Main container for the command bar
        # Using QHBoxLayout to place the QTextEdit and QPushButton side-by-side
        self.command_bar_layout = QHBoxLayout() 
        self.command_bar_layout.setContentsMargins(2, 2, 2, 2) # Small margins
        self.command_bar_layout.setSpacing(2) # Small spacing
        self.command_bar_widget.setLayout(self.command_bar_layout)

        self.command_bar = QTextEdit(self) # Multi-line input for AI commands
        self.command_bar.setPlaceholderText("AI Command (Ctrl+Enter to send)")
        self.command_bar.setFixedHeight(60) # Fixed height for the command bar input
        # self.command_bar.hide() # Initially hidden, shown by action/shortcut

        self.send_button = QPushButton("Send", self)
        self.send_button.clicked.connect(self.execute_command)
        
        self.command_bar_layout.addWidget(self.command_bar)
        self.command_bar_layout.addWidget(self.send_button)
        self.command_bar_widget.hide() # Hide the whole widget initially

        # Shortcut to show/focus the command bar
        self.command_shortcut = QAction("AI Command Bar Shortcut", self) # Name for the action
        self.command_shortcut.setShortcut(QKeySequence("Ctrl+Shift+Space"))
        self.command_shortcut.triggered.connect(self.show_command_bar)
        self.addAction(self.command_shortcut) # Add action to the main window

        # Connect key press event for Ctrl+Enter functionality
        self.command_bar.keyPressEvent = self.command_bar_key_press_event

    def _get_unique_filename(self, directory: Path, original_filename: str) -> Path:
        """
        Generates a unique filename in the given directory.
        If 'original_filename' exists, appends a counter (e.g., image_1.png).
        """
        filepath = directory / original_filename
        if not filepath.exists():
            return filepath

        name, ext = os.path.splitext(original_filename)
        counter = 1
        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_filepath = directory / new_filename
            if not new_filepath.exists():
                return new_filepath
            counter += 1

    def _get_unique_asset_filename(self, directory: Path, ext: str) -> Path:
        """
        Generates a unique filename in the given directory using a random hash.
        Args:
            directory (Path): The directory to save the file in.
            ext (str): The file extension (with dot), e.g., '.png'.
        Returns:
            Path: The full path to a unique file.
        """
        while True:
            rand_hash = secrets.token_urlsafe(12)
            filename = f"{rand_hash}{ext}"
            filepath = directory / filename
            if not filepath.exists():
                return filepath

    def _on_editor_content_changed(self):
        is_dirty = self.editor.toPlainText() != self.last_saved_text
        self.set_dirty(is_dirty)
        # Do NOT call self.update_preview() here; preview only updates on mode switch
        self.update_language_label()

    def _update_window_title(self, filename: str | None = None, dirty: bool = False):
        if filename:
            base_title = f"Marknote - {Path(filename).name}"
        else:
            base_title = "Marknote - Untitled"
        self.setWindowTitle(f"{base_title}{' *' if dirty else ''}")

    def _update_file_state(self, content: str, filepath: str | None = None, dirty: bool = False):
        self.last_saved_text = content
        self.current_file = filepath
        self._update_window_title(filepath, dirty)
        self.update_preview()

    def set_dirty(self, dirty: bool):
        self._update_window_title(self.current_file, dirty)

    def open_file(self, file_path: str | None = None):
        """
        Opens a Markdown file, loading its content into the editor.

        Args:
            file_path (str | None, optional): The path to the file to open.
                If None, a file dialog is shown. Defaults to None.
        """
        if not self.maybe_save_changes(): # Check for unsaved changes
            return

        if not file_path: # If no path provided, show dialog
            # Start dialog in the default folder, filter for Markdown files
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Markdown File", self.default_folder, 
                "Markdown Files (*.md);;All Files (*)"
            )
        
        if file_path: # Proceed if a file path was selected or provided
            try:
                resolved_path = str(Path(file_path).resolve()) # Normalize the path
                with open(resolved_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                self.editor.setPlainText(content)
                self._update_file_state(content, resolved_path, False)
                self.recent_files_manager.add_to_recent_files(resolved_path)
                self.update_recent_files_menu()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def open_folder(self):
        """Opens a folder, setting it as the new default document library root."""
        # Start dialog from the current default folder
        folder_path_str = QFileDialog.getExistingDirectory(self, "Open Folder", str(self.default_folder))
        if folder_path_str:
            self.default_folder = str(Path(folder_path_str).resolve()) # Normalize and store
            
            # Persist the new default folder to application configuration
            config = load_app_config()
            config[CONFIG_KEY_DEFAULT_NOTES_FOLDER] = self.default_folder
            save_app_config(config) # Handles its own error reporting
            
            self.refresh_library() # Refresh the file library view

    def open_tree_item(self, item: QTreeWidgetItem, column: int):

        """
        Handles clicks on items in the file library tree.
        Opens files or expands/collapses folders.

        Args:
            item (QTreeWidgetItem): The clicked tree item.
            column (int): The column of the clicked item (usually 0).
        """
        path_str = item.data(0, Qt.ItemDataRole.UserRole + 1) # Retrieve path stored in item data
        if not path_str: return

        path = Path(path_str)
        if path.is_dir():
            # Toggle expand/collapse for directories
            if item.isExpanded():
                self.library.collapseItem(item)
            else:
                self.library.expandItem(item)
            
            # When a folder is clicked, clear editor and show a message
            if not self.maybe_save_changes(): return # Check unsaved changes
            self.editor.setReadOnly(True)
            self.editor.setPlainText("Select a file to edit or create a new file in this folder.")
            self.preview.set_markdown("") # Clear preview
            self.current_file = None
            self.last_saved_text = "" # Reset last saved text
        elif path.is_file() and path.suffix.lower() == ".md":
            # If a .md file is clicked, open it
            self.open_file(str(path)) # open_file handles maybe_save_changes
            self.editor.setReadOnly(False) # Ensure editor is writable

    def load_markdown_file(self, path_str: str):
        """
        Loads content from a given Markdown file path into the editor.
        This is a direct load, usually called internally.

        Args:
            path_str (str): The absolute path to the Markdown file.
        """
        try:
            path = Path(path_str).resolve() # Ensure path is absolute and resolved
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            self.editor.setPlainText(content)
            self._update_file_state(content, str(path), False)
            self.save_last_note(str(path)) # Update last opened note in config
            self.update_preview() # <-- ensure preview is updated with correct base_url
            self.set_dirty(False) # Reset dirty state
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file: {e}")
    
    def save_file(self):
        """Saves the current content of the editor to the current_file path."""
        text_content = self.editor.toPlainText()
        if self.current_file:
            try:
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(text_content)
                self._update_file_state(text_content, self.current_file, False)
                self.recent_files_manager.add_to_recent_files(self.current_file)
                self.update_recent_files_menu()
                self.set_dirty(False) # Reset dirty state
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
        else:
            # If no current file, trigger "Save As" dialog
            self.save_file_as()
        self.update_preview()

    def save_file_as(self):
        """Saves the current editor content to a new file, chosen via a dialog."""
        # Start dialog in default folder, suggest current filename if available
        suggested_name = Path(self.current_file).name if self.current_file else "untitled.md"
        default_save_path = str(Path(self.default_folder) / suggested_name)

        file_path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Markdown File As", default_save_path, 
            "Markdown Files (*.md);;All Files (*)"
        )
        
        if file_path_str:
            # Ensure .md extension
            if not file_path_str.lower().endswith('.md'):
                file_path_str += '.md'
            
            self.current_file = str(Path(file_path_str).resolve()) # Update current file to new path
            self.save_file() # Call save_file, which will now use the new current_file
            self.update_preview()
                             # This also handles adding to recent files and updating title.

    def refresh_library(self, filter_text: str = ""):
        """
        Refreshes the document library tree view.

        Populates the tree with files and folders from the default_folder,
        optionally filtering by filter_text.

        Args:
            filter_text (str, optional): Text to filter items by. Defaults to "".
        """
        self.library.clear() # Clear existing items
        base_path = Path(self.default_folder)

        # Recursive function to add items to the tree
        def add_items_recursive(parent_widget_item: QTreeWidgetItem, current_dir: Path):
            try:
                # Sort entries: folders first, then files, all case-insensitive
                entries = sorted(
                    current_dir.iterdir(), 
                    key=lambda x: (not x.is_dir(), x.name.lower())
                )
                for entry in entries:
                    # Apply filter only to file names, not directories
                    if entry.is_file() and filter_text.lower() not in entry.name.lower():
                        continue

                    item = QTreeWidgetItem([entry.name])
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, str(entry.resolve())) # Store full path
                    
                    # Set icon based on type (optional, requires QIcon setup)
                    # if entry.is_dir():
                    #     item.setIcon(0, QIcon.style().standardIcon(QStyle.SP_DirIcon))
                    # else:
                    #     item.setIcon(0, QIcon.style().standardIcon(QStyle.SP_FileIcon))

                    parent_widget_item.addChild(item)
                    if entry.is_dir():
                        add_items_recursive(item, entry) # Recurse for subdirectories
            except Exception as e:
                # Log or display error if a directory can't be accessed
                print(f"Error reading directory {current_dir}: {e}")
        
        # Create a root item for the library (e.g., "Documents" or base_path.name)
        # Using a simple name for the root node for cleaner display
        display_root_name = base_path.name if base_path.name else str(base_path)
        root_tree_item = QTreeWidgetItem([display_root_name])
        root_tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, str(base_path.resolve()))
        # root_tree_item.setIcon(0, QIcon.style().standardIcon(QStyle.SP_DriveHDIcon)) # Example icon

        add_items_recursive(root_tree_item, base_path)
        self.library.addTopLevelItem(root_tree_item)
        self.library.expandAll() # Expand all items by default

    def filter_library(self, text: str):
        """
        Filters the document library based on the provided text.
        Called when the search bar text changes.

        Args:
            text (str): The text to filter by.
        """
        self.refresh_library(filter_text=text)

    def create_folder(self):
        """Creates a new folder in the current default_folder after prompting for a name."""
        if not self.maybe_save_changes(): return

        folder_name, ok = QInputDialog.getText(self, "Create Folder", "Folder name:")
        if ok and folder_name.strip():
            try:
                new_folder_path = Path(self.default_folder) / folder_name.strip()
                new_folder_path.mkdir(parents=True, exist_ok=True) # Create folder
                
                # Create a default "untitled.md" or "readme.md" in the new folder
                # This provides an immediate file to select/edit.
                default_md_path = new_folder_path / "untitled.md" 
                with open(default_md_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {folder_name.strip()}\n\n") # Basic content
                
                self.refresh_library(self.search_bar.text()) # Refresh to show new folder
                self.load_markdown_file(str(default_md_path)) # Open the new default file
                self.editor.setReadOnly(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create folder or default file: {e}")

    def new_file(self):
        """Creates a new, empty file in the editor."""
        if self.maybe_save_changes():
            self.editor.clear()
            self._update_file_state("", None, False)

    def maybe_save_changes(self) -> bool:
        """
        Checks for unsaved changes and prompts the user to save if necessary.

        Returns:
            bool: True if processing should continue (changes saved or no changes), 
                  False if the operation should be aborted (user cancelled or save failed).
        """
        if self.editor.isReadOnly(): # No changes if read-only
            return True
        
        current_text = self.editor.toPlainText()
        if current_text != self.last_saved_text:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_file()
                # Check if save was successful (or if user cancelled save_file_as dialog)
                if self.editor.toPlainText() != self.last_saved_text:
                    return False # Save failed or was cancelled
            elif reply == QMessageBox.StandardButton.Cancel:
                return False # User chose to cancel the operation
            # If reply is No, proceed without saving (changes will be lost)
        return True

    def show_context_menu(self, position: QPoint): # Added type hint
        """
        Shows a context menu in the editor with AI-related actions.

        Args:
            position (QPoint): The position where the context menu was requested.
        """
        menu = QMenu(self)
        # AI Actions
        expand_action = menu.addAction("Expand with AI")
        refine_action = menu.addAction("Refine with AI")
        analyze_action = menu.addAction("Analyze Document with AI")
        menu.addSeparator()
        # --- New AI Actions ---
        ai_summary_action = menu.addAction("Summarize Page")
        ai_autolink_action = menu.addAction("Auto-Link Page")
        ai_related_action = menu.addAction("Find Related Pages")
        ai_semantic_search_action = menu.addAction("Semantic Search")
        menu.addSeparator()
        # Command Bar Actions
        command_bar_action = menu.addAction("Show AI Command Bar")
        # nlp_command_action = menu.addAction("AI Command (Natural Language)") # This seems redundant if command bar handles NLP

        # Connect actions to methods
        expand_action.triggered.connect(self.expand_selected_text)
        refine_action.triggered.connect(self.refine_selected_text)
        analyze_action.triggered.connect(self.analyze_document)
        ai_summary_action.triggered.connect(self.ai_summarize_page)
        ai_autolink_action.triggered.connect(self.ai_autolink_page)
        ai_related_action.triggered.connect(self.ai_find_related_pages)
        ai_semantic_search_action.triggered.connect(self.ai_semantic_search)
        command_bar_action.triggered.connect(self.show_command_bar)
        # nlp_command_action.triggered.connect(self.show_command_bar)

        menu.addSeparator()
        ai_analyze_table_action = menu.addAction("AI Analyze Table")
        ai_analyze_table_action.setEnabled(self.editor.hasSelectedText())
        ai_analyze_table_action.triggered.connect(self.ai_analyze_selected_table)
        
        menu.exec(self.editor.mapToGlobal(position)) # Show menu at global cursor position

    def show_library_context_menu(self, position: QPoint): # Added type hint
        """
        Shows a context menu in the document library for file/folder operations.

        Args:
            position (QPoint): The position where the context menu was requested.
        """
        item = self.library.itemAt(position) # Get the item at the click position
        if not item: return

        path_str = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not path_str: return
        
        path = Path(path_str)
        menu = QMenu(self)

        if path.is_dir():
            new_file_action = menu.addAction("New File in Folder")
            rename_action = menu.addAction("Rename Folder")
            delete_action = menu.addAction("Delete Folder")
            
            new_file_action.triggered.connect(lambda: self.create_file_in_folder(str(path)))
            rename_action.triggered.connect(lambda: self.rename_file_or_folder(item, str(path), is_folder=True))
            delete_action.triggered.connect(lambda: self.delete_file_or_folder(item, str(path), is_folder=True))
        else: # It's a file
            rename_action = menu.addAction("Rename File")
            delete_action = menu.addAction("Delete File")

            rename_action.triggered.connect(lambda: self.rename_file_or_folder(item, str(path), is_folder=False))
            delete_action.triggered.connect(lambda: self.delete_file_or_folder(item, str(path), is_folder=False))
        
        menu.exec(self.library.viewport().mapToGlobal(position)) # Show at global position

    def rename_file_or_folder(self, item: QTreeWidgetItem, path_str: str, is_folder: bool):
        """
        Renames a file or folder.

        Args:
            item (QTreeWidgetItem): The tree item being renamed (currently unused but good for context).
            path_str (str): The current path of the file or folder.
            is_folder (bool): True if renaming a folder, False for a file.
        """
        path = Path(path_str)
        old_name = path.name
        
        prompt_text = f"Enter new name for {'folder' if is_folder else 'file'}:"
        new_name, ok = QInputDialog.getText(self, "Rename", prompt_text, text=old_name)
        
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_path = path.parent / new_name.strip()
            # For files, ensure .md extension is preserved or added if necessary
            if not is_folder and path.suffix.lower() == '.md' and not new_path.suffix.lower() == '.md':
                new_path = new_path.with_suffix('.md')

            if new_path.exists():
                QMessageBox.warning(self, "Rename Error", f"A file or folder named '{new_name.strip()}' already exists.")
                return
            try:
                path.rename(new_path) # Perform rename operation
                self.refresh_library(self.search_bar.text()) # Refresh library view
                # If the currently open file was renamed, update its path
                if self.current_file == str(path):
                    self.current_file = str(new_path)
                    self._update_window_title(new_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename: {e}")

    def create_file_in_folder(self, folder_path_str: str):
        """
        Creates a new .md file within the specified folder.

        Args:
            folder_path_str (str): The path to the folder where the file will be created.
        """
        if not self.maybe_save_changes(): return

        file_name, ok = QInputDialog.getText(self, "New File", "Enter new file name (e.g., my_note.md):")
        if ok and file_name.strip():
            # Ensure .md extension
            if not file_name.strip().lower().endswith('.md'):
                file_name = file_name.strip() + '.md'
            
            new_file_path = Path(folder_path_str) / file_name
            if new_file_path.exists():
                QMessageBox.warning(self, "File Exists", f"A file named '{file_name}' already exists in this folder.")
                return
            
            try:
                with open(new_file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {Path(file_name).stem}\n\n") # Initial content
                
                self.refresh_library(self.search_bar.text())
                self.load_markdown_file(str(new_file_path)) # Open the new file
                self.editor.setReadOnly(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create file: {e}")

    def ai_prompt_action(self, action_type: str):
        """Unified handler for all AI prompt-based actions."""
        if not self.ai:
            from config_utils import load_gemini_api_key
            api_key = load_gemini_api_key()
            if not api_key:
                QMessageBox.warning(self, "API Key Missing", "Gemini API key not found. Please set it in Preferences.")
                return
            self.ai = AIMarkdownAssistant(api_key)

        prompt_map = {
            'table': {
                'label': "Describe the table you want to create:",
                'ai_method': self.ai.create_table,
                'success_msg': "AI table created successfully.",
                'fail_msg': "AI Table Creation Failed"
            },
            'mermaid': {
                'label': "Describe the diagram you want to create:",
                'ai_method': self.ai.create_mermaid_diagram,
                'success_msg': "AI Mermaid diagram created successfully.",
                'fail_msg': "AI Mermaid Diagram Creation Failed"
            },
            'command': {
                'label': "Enter your AI command:",
                'ai_method': lambda desc: self.ai.process_natural_command(desc, selected_text=self.editor.selectedText() or None),
                'success_msg': "AI command executed.",
                'fail_msg': "AI Command Failed"
            }
        }
        if action_type not in prompt_map:
            QMessageBox.critical(self, "AI Error", f"Unknown AI action: {action_type}")
            return
        label = prompt_map[action_type]['label']
        ai_method = prompt_map[action_type]['ai_method']
        success_msg = prompt_map[action_type]['success_msg']
        fail_msg = prompt_map[action_type]['fail_msg']
        prompt, ok = AIPromptDialog.get_prompt_from_user(label, self)
        if not ok:
            self.statusBar().showMessage(f"{action_type.capitalize()} creation cancelled.", 3000)
            return
        if not prompt:
            QMessageBox.information(self, "No Description", f"{action_type.capitalize()} description cannot be empty.")
            self.statusBar().showMessage(f"{action_type.capitalize()} creation cancelled: no description.", 3000)
            return
        try:
            self.statusBar().showMessage(f"AI is generating {action_type}...", 3000)
            result = ai_method(prompt)
            if result and not result.startswith("Error:") and not result.startswith("Failed to get valid response"):
                # Insert or replace selection for command, always insert for table/mermaid
                if action_type == 'command' and self.editor.selectedText():
                    self.editor.replaceSelectedText(result)
                else:
                    self.editor.insert(result + "\n")
                self.statusBar().showMessage(success_msg, 3000)
                self.set_dirty(True)
            else:
                QMessageBox.critical(self, fail_msg, f"Could not generate result. AI response:\n{result}")
                self.statusBar().showMessage(fail_msg, 3000)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "AI Error", f"An unexpected error occurred: {e}")
            self.statusBar().showMessage(f"Error during {action_type} creation.", 3000)

    def ai_create_table(self):
        self.ai_prompt_action('table')
    def ai_create_mermaid_diagram(self):
        self.ai_prompt_action('mermaid')
    def execute_command(self):
        self.ai_prompt_action('command')

    def ai_analyze_selected_table(self):
        """Analyzes the selected Markdown table using AI and displays insights."""
        selected_text = self.editor.selectedText()
        if not selected_text:
            QMessageBox.information(self, "No Selection", "Please select a Markdown table to analyze.")
            self.statusBar().showMessage("AI Table Analysis: No text selected.", 3000)
            return

        if not self.ai:
            api_key = load_gemini_api_key()
            if not api_key:
                QMessageBox.warning(self, "API Key Missing", 
                                    "Gemini API key not found. Please set it in Preferences.")
                return
            self.ai = AIMarkdownAssistant(api_key)

        try:
            self.statusBar().showMessage("AI is analyzing table...", 3000)
            analysis_result = self.ai.analyze_table(selected_text)

            if analysis_result and not analysis_result.startswith("Error:") and not analysis_result.startswith("Failed to get valid response"):
                # Display the analysis in a message box. 
                # Analysis might be long, so consider a scrollable dialog for future improvement.
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("AI Table Analysis")
                msg_box.setTextFormat(Qt.TextFormat.MarkdownText) # Render analysis as Markdown
                msg_box.setText(analysis_result)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()
                self.statusBar().showMessage("AI table analysis complete.", 3000)
            else:
                QMessageBox.critical(self, "AI Table Analysis Failed", 
                                     f"Could not analyze table. AI response:\n{analysis_result}")
                self.statusBar().showMessage("AI table analysis failed.", 3000)
        except Exception as e:
            logger.error(f"Error during AI table analysis: {e}")
            QMessageBox.critical(self, "AI Error", f"An unexpected error occurred during table analysis: {e}")
            self.statusBar().showMessage("Error during AI table analysis.", 3000)

    def delete_file_or_folder(self, item: QTreeWidgetItem, path_str: str, is_folder: bool):
        """
        Deletes a file or an empty folder.

        Args:
            item (QTreeWidgetItem): The tree item being deleted.
            path_str (str): The path of the file or folder.
            is_folder (bool): True if deleting a folder, False for a file.
        """
        path = Path(path_str)
        type_name = "folder" if is_folder else "file"
        
        if is_folder:
            # Check if folder is empty (excluding system files like .DS_Store)
            try:
                if any(entry for entry in path.iterdir() if entry.name not in ['.DS_Store']): # macOS specific
                    QMessageBox.warning(
                        self, "Cannot Delete Folder",
                        f"Folder '{path.name}' is not empty. Please delete its contents first."
                    )
                    return
            except OSError as e:
                 QMessageBox.warning(self, "Error", f"Could not check folder contents: {e}")
                 return

        reply = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to permanently delete this {type_name}?\n\n{path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No # Default to No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if is_folder:
                    path.rmdir() # Remove empty directory
                else:
                    path.unlink() # Remove file
                
                # If the deleted item was the currently open file or a folder containing it
                if self.current_file:
                    current_file_path = Path(self.current_file)
                    if (not is_folder and current_file_path == path) or \
                       (is_folder and path in current_file_path.parents):
                        self.new_file() # Effectively clears the editor and resets state

                self.refresh_library(self.search_bar.text())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete {type_name}: {e}")

    def expand_selected_text(self):
        """Expands the selected text using the AI assistant."""
        selected_text = self.editor.selectedText()
        if selected_text:
            expanded_content = self.ai.expand_content(selected_text)
            self.editor.replaceSelectedText(expanded_content) # Replace selection with AI output

    def refine_selected_text(self):
        """Refines the selected text for clarity and conciseness using the AI assistant."""
        selected_text = self.editor.selectedText()
        if selected_text:
            refined_content = self.ai.refine_writing(selected_text)
            self.editor.replaceSelectedText(refined_content)

    def analyze_document(self):
        """Analyzes the entire document content using the AI assistant and shows results."""
        full_text = self.editor.toPlainText()
        if not full_text.strip():
            QMessageBox.information(self, "AI Document Analysis", "The document is empty.")
            return
        analysis_results = self.ai.analyze_document(full_text)
        QMessageBox.information(self, "AI Document Analysis", analysis_results)

    def show_command_bar(self):
        """Shows the AI command bar and sets focus to it."""
        if self.command_bar_widget.isHidden():
            self.command_bar_widget.show()
            self.command_bar.setFocus() # Set focus to the input field
        else:
            self.command_bar_widget.hide()


    def update_recent_files_menu(self):
        """Updates the 'Open Recent' menu with the list from RecentFilesManager."""
        self.recent_files_menu.clear()
        if not self.recent_files_manager.recent_files_list:
            no_recent_action = QAction("(No recent files)", self)
            no_recent_action.setEnabled(False)
            self.recent_files_menu.addAction(no_recent_action)
            return

        for file_path_str in self.recent_files_manager.recent_files_list:
            path = Path(file_path_str)
            # Display only the filename in the menu
            action = QAction(path.name, self) 
            action.setData(str(path)) # Store full path in action's data
            action.triggered.connect(self.open_recent_file_action)
            self.recent_files_menu.addAction(action)

    def open_recent_file_action(self):
        """Action triggered when a recent file is selected from the menu."""
        action = self.sender() # Get the action that triggered the signal
        if isinstance(action, QAction): # Type check
            file_path_str = action.data()
            if file_path_str:
                self.open_file(file_path_str) # Call open_file with the stored path

    def export_file_as(self):
        """Exports the current document as HTML or Plain Text."""
        if not self.editor.toPlainText().strip():
            QMessageBox.information(self, "Export As", "There is no content to export.")
            return

        # Suggest a filename based on the current file or "untitled"
        base_filename = Path(self.current_file).stem if self.current_file else "untitled"
        suggested_path = Path(self.default_folder) / base_filename

        file_path_str, selected_filter = QFileDialog.getSaveFileName(
            self, "Export File As", str(suggested_path),
            "HTML Document (*.html);;Plain Text (*.txt)"
        )

        if not file_path_str: return # User cancelled

        path_to_save = Path(file_path_str)
        content_to_save = ""
        current_markdown_text = self.editor.toPlainText()

        try:
            if "(*.html)" in selected_filter:
                # Ensure .html extension
                if path_to_save.suffix.lower() != ".html":
                    path_to_save = path_to_save.with_suffix(".html")
                
                # Convert Markdown to HTML (basic conversion, similar to preview)
                html_content = markdown.markdown(current_markdown_text, extensions=['fenced_code'])
                # Simple HTML wrapper with basic styling
                content_to_save = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Exported: {Path(self.current_file).name if self.current_file else "Untitled"}</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; line-height: 1.6; 
                background-color: #fdfdfd; color: #333; }}
        code {{ background-color: #f0f0f0; padding: 2px 4px; border-radius: 3px; 
                font-family: monospace; }}
        pre {{ background-color: #f0f0f0; padding: 10px; border-radius: 3px; 
               overflow-x: auto; white-space: pre-wrap; }}
        /* Add other styles as needed, e.g., for blockquotes, tables */
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
            elif "(*.txt)" in selected_filter:
                # Ensure .txt extension
                if path_to_save.suffix.lower() != ".txt":
                    path_to_save = path_to_save.with_suffix(".txt")
                content_to_save = current_markdown_text
            else:
                QMessageBox.warning(self, "Export Error", "Invalid file type selected.")
                return

            with open(path_to_save, 'w', encoding='utf-8') as f:
                f.write(content_to_save)
            QMessageBox.information(self, "Export Successful", f"File exported successfully to {path_to_save}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not export file: {e}")

    def close_application(self):
        """Closes the application, triggering the closeEvent."""
        self.close() 

    def show_syntax_help(self):
        """Displays a QMessageBox with Markdown and Mermaid syntax help."""
        help_text = (
            "<b>Markdown Syntax:</b><br>"
            "<ul>"
            "<li><b>Bold:</b> <code>**bold text**</code> or <code>__bold text__</code></li>"
            "<li><b>Italic:</b> <code>*italic text*</code> or <code>_italic text_</code></li>"
            "<li><b>Heading:</b> <code># H1</code>, <code>## H2</code>, <code>### H3</code></li>"
            "<li><b>Unordered List:</b> <code>- Item 1</code><br><code>  - Subitem</code></li>"
            "<li><b>Ordered List:</b> <code>1. Item 1</code><br><code>   1. Subitem</code></li>"
            "<li><b>Link:</b> <code>[Link Text](https://example.com)</code></li>"
            "<li><b>Image:</b> <code>![Alt Text](image_url_or_path.png)</code></li>"
            "<li><b>Inline Code:</b> <code>`code here`</code></li>"
            "<li><b>Code Block:</b><br><pre>```python\nprint('Hello')\n```</pre></li>"
            "<li><b>Blockquote:</b> <code>> Quoted text</code></li>"
            "<li><b>Horizontal Rule:</b> <code>---</code> or <code>***</code></li>"
            "</ul>"
            "<b>Mermaid Diagram Syntax:</b><br>"
            "Enclose Mermaid syntax in a code block marked with `mermaid`:"
            "<pre>```mermaid\ngraph TD\n  A[Start] --> B{Decision}\n  B -- Yes --> C[End]\n  B -- No --> D[Alternative]\n```</pre>"
            "For more details, see the <a href='https://mermaid.js.org/intro/'>official Mermaid documentation</a>."
        )
        # Use QMessageBox.about for rich text display
        QMessageBox.about(self, "Markdown & Mermaid Syntax Guide", help_text)


    def _open_settings_dialog(self):
        """Opens the settings/preferences dialog and applies changes if accepted."""
        if SettingsDialog.get_settings(self):
            # Settings were saved, reload config and apply them
            config = load_app_config()
            # Apply editor font settings
            font_family = config.get(CONFIG_KEY_EDITOR_FONT_FAMILY, "Arial")
            font_size = config.get(CONFIG_KEY_EDITOR_FONT_SIZE, 12)
            new_font = QFont(font_family, font_size)
            self.editor.setFont(new_font)
            if self.editor.lexer():
                self.editor.lexer().setDefaultFont(new_font)
            self.editor.setMarginsFont(new_font)
            # Apply default notes folder setting
            new_default_folder = config.get(CONFIG_KEY_DEFAULT_NOTES_FOLDER)
            if new_default_folder and Path(new_default_folder).is_dir() and new_default_folder != self.default_folder:
                self.default_folder = new_default_folder
                self.refresh_library()
                QMessageBox.information(self, "Settings Applied", f"Default notes folder changed to: {new_default_folder}\nEditor font updated.")
            else:
                QMessageBox.information(self, "Settings Applied", "Editor font updated.")
            # Apply sidebar visibility immediately
            sidebar_visible = config.get(CONFIG_KEY_SIDEBAR_VISIBLE, True)
            self.library_panel.setVisible(sidebar_visible)
            if hasattr(self, 'toggle_sidebar_action'):
                self.toggle_sidebar_action.setChecked(sidebar_visible)
        else:
            # Dialog was cancelled, or an error occurred during save in dialog
            pass # Optionally, log or inform user if specific feedback is needed

    def _normalize_path(self, path_str: str | None) -> str:
        """
        Normalizes a path string using pathlib for robustness and platform-independence.
        If the path is None or empty, returns a default path.

        Args:
            path_str (str | None): The path string to normalize.

        Returns:
            str: The normalized, absolute path string.
        """
        # Define a sensible default path, e.g., in user's Documents
        default_path = Path.home() / 'Documents' / 'Marknote'
        
        if not path_str: # Handles None or empty string
            return str(default_path.resolve()) # Ensure default is also resolved
        
        try:
            # Expand user directory (e.g., ~) and resolve to an absolute, canonical path
            # This also handles normalization of separators (e.g., / vs \) and . or .. components.
            normalized_path = Path(path_str).expanduser().resolve()
            return str(normalized_path)
        except RuntimeError: 
            # Path resolution can fail on some systems for certain invalid paths
            # Example: Path("CON").resolve() on Windows.
            # Fallback to default path in such rare cases.
            return str(default_path.resolve())
        except Exception: 
            # Catch any other unexpected errors during path normalization.
            # This is a safeguard; specific errors should be rare with Path.resolve().
            return str(default_path.resolve())


    def get_or_create_default_folder(self) -> str:
        """
        Determines the default folder for storing notes.
        
        It tries to load from config, validates it, and if not found or invalid,
        prompts the user to choose or create one.

        Returns:
            str: The absolute path to the determined default folder.
        """
        config = load_app_config()
        config_default_folder_str = config.get(CONFIG_KEY_DEFAULT_NOTES_FOLDER)
        
        if config_default_folder_str:
            normalized_path_from_config = Path(self._normalize_path(config_default_folder_str))
            try:
                # Attempt to create the folder (and any necessary parents)
                # exist_ok=True means it won't raise an error if the directory already exists.
                normalized_path_from_config.mkdir(parents=True, exist_ok=True)
                
                if normalized_path_from_config.is_dir(): # Check if it's actually a directory
                    # If normalization changed the path string, update the config
                    if str(normalized_path_from_config) != config_default_folder_str:
                        config[CONFIG_KEY_DEFAULT_NOTES_FOLDER] = str(normalized_path_from_config)
                        save_app_config(config)
                    return str(normalized_path_from_config)
                else:
                    # This case occurs if the path exists but is not a directory,
                    # or if mkdir somehow failed silently to make it a directory.
                    raise OSError(f"Path '{normalized_path_from_config}' exists but is not a valid directory.")
            except OSError as e:
                # Show a warning if the configured path is problematic
                QMessageBox.warning(self, "Default Folder Error",
                                    f"The configured default folder '{normalized_path_from_config}' "
                                    f"could not be used or created:\n{e}\n"
                                    "A new default folder will be set up.")
        
        # If no valid path from config (initially missing, or failed validation), prompt user
        return self._prompt_and_set_new_default_folder(config)

    def _prompt_and_set_new_default_folder(self, config: dict) -> str:
        """
        Prompts the user to select or create a default folder, then saves it to the configuration.
        This method is called when the initial default folder setup fails or is missing.

        Args:
            config (dict): The application configuration dictionary.

        Returns:
            str: The absolute path to the newly set default folder.
        """
        user_choice = QMessageBox.question(
            self, "Default Folder Setup",
            "No default folder is set, or the previous one was invalid.\n\n"
            "Would you like to use the system default '~/Documents/Marknote'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes # Default to Yes
        )

        chosen_path_str: str
        if user_choice == QMessageBox.StandardButton.Yes:
            chosen_path_str = str(Path.home() / 'Documents' / 'Marknote')
        else:
            # Allow user to select an existing directory
            dialog_path = QFileDialog.getExistingDirectory(
                self, "Select Default Folder for Marknote", str(Path.home())
            )
            if dialog_path:
                chosen_path_str = dialog_path
            else: # User cancelled the dialog
                chosen_path_str = str(Path.home() / 'Documents' / 'Marknote')
                QMessageBox.information(self, "Default Folder Set", 
                                        f"No folder selected. Using system default: {chosen_path_str}")
        
        final_chosen_path = Path(self._normalize_path(chosen_path_str))

        try:
            final_chosen_path.mkdir(parents=True, exist_ok=True)
            if not final_chosen_path.is_dir():
                raise OSError(f"Chosen path '{final_chosen_path}' could not be established as a directory.")
            
            config[CONFIG_KEY_DEFAULT_NOTES_FOLDER] = str(final_chosen_path)
            if not save_app_config(config):
                # save_app_config should show its own error, but we can log here too.
                print(f"Warning: Failed to save new default folder {final_chosen_path} to config.")
            return str(final_chosen_path)
        except OSError as e:
            # Critical error if the chosen/default path cannot be created
            QMessageBox.critical(self, "Fatal Default Folder Error",
                                 f"Could not create or use the chosen default folder '{final_chosen_path}':\n{e}\n"
                                 "Marknote will use a temporary fallback in your home directory.")
            
            # Fallback to a temporary directory in user's home
            fallback_path = Path.home() / "Marknote_Temp_Default"
            try:
                fallback_path.mkdir(parents=True, exist_ok=True)
                QMessageBox.information(self, "Using Fallback Folder", 
                                        f"Marknote is using a temporary folder: {fallback_path}")
                return str(fallback_path)
            except Exception as fallback_e:
                # If even the temporary fallback fails, use user's home as an absolute last resort
                QMessageBox.critical(self, "Critical Error", 
                                     f"Failed to create even a temporary fallback folder: {fallback_e}\n"
                                     f"Marknote will use your home directory: {str(Path.home())}")
                return str(Path.home())

    def save_last_note(self, path_str: str):
        """
        Saves the path of the last opened note to the application configuration.

        Args:
            path_str (str): The path to the last opened note.
        """
        config = load_app_config()
        # Normalize the path before saving to ensure consistency
        normalized_path = self._normalize_path(path_str)
        
        if normalized_path and Path(normalized_path).is_file(): # Ensure it's a valid file path
            config[CONFIG_KEY_LAST_NOTE] = normalized_path
            save_app_config(config) 
        else:
            # If path is invalid or becomes empty after normalization, remove from config
            if CONFIG_KEY_LAST_NOTE in config:
                del config[CONFIG_KEY_LAST_NOTE]
                save_app_config(config)
            print(f"Warning: Attempted to save an invalid path for last note: {path_str}")

    def handle_pasted_image_url(self, url: str):
        print(f"*** MARKNOTE PASTE DEBUG: handle_pasted_image_url CALLED with URL: {url}")
        if not self.current_file:
            QMessageBox.warning(self, "Save Note First", 
                                "Please save your note before pasting an image URL. "
                                "The image will be saved relative to the note's location.")
            alt_text, ok = QInputDialog.getText(self, "Link Text", f"Note not saved. Enter link text for {url}:", text=url.split('/')[-1])
            if ok:
                self.editor.insert(f"[{alt_text}]({url})")
            else:
                self.editor.insert(url)
            self.set_dirty(True)
            self.update_preview()
            return

        try:
            current_note_path = Path(self.current_file)
            assets_dir = current_note_path.parent / "_assets" / "images"
            assets_dir.mkdir(parents=True, exist_ok=True)

            print(f"*** MARKNOTE PASTE DEBUG: Downloading image from {url}")
            response = requests.get(url, timeout=10, stream=True)
            response.raise_for_status()

            # Determine extension from Content-Type or URL
            parsed_qurl = QUrl(url)
            url_path = parsed_qurl.path().lower()
            url_ext = os.path.splitext(url_path)[1]
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}
            image_extensions_map = {
                'image/jpeg': '.jpg', 'image/jpg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/webp': '.webp',
                'image/svg+xml': '.svg',
                'image/bmp': '.bmp'
            }
            content_type = response.headers.get('Content-Type', '').lower().split(';')[0].strip()
            if content_type in image_extensions_map:
                ext = image_extensions_map[content_type]
            elif url_ext in image_extensions:
                ext = url_ext
            else:
                ext = '.png'  # fallback

            local_filepath = self._get_unique_asset_filename(assets_dir, ext)
            print(f"*** MARKNOTE PASTE DEBUG: Saving image to {local_filepath}")

            with open(local_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"*** MARKNOTE PASTE DEBUG: Image saved successfully to {local_filepath}")

            alt_text, ok = QInputDialog.getText(self, "Image Alt Text", "Enter alt text for the image:", text=local_filepath.stem)
            if ok:
                relative_path = Path("_assets") / "images" / local_filepath.name
                markdown_image_tag = f"![{alt_text}]({relative_path.as_posix()})"
                self.editor.insert(markdown_image_tag)
                self.set_dirty(True)
                self.update_preview()
            else:
                print("*** MARKNOTE PASTE DEBUG: Alt text cancelled, removing downloaded image and inserting URL as link.")
                local_filepath.unlink(missing_ok=True)
                link_text_fallback, link_ok = QInputDialog.getText(self, "Link Text", f"Alt text cancelled. Enter link text for {url}:", text=url.split('/')[-1])
                if link_ok:
                    self.editor.insert(f"[{link_text_fallback}]({url})")
                else:
                    self.editor.insert(url)
                self.set_dirty(True)
                self.update_preview()

        except requests.RequestException as e:
            print(f"Error downloading image {url}: {e}")
            QMessageBox.warning(self, "Download Error", f"Failed to download image: {e}\n\nURL will be pasted as plain text.")
            self.editor.insert(url)
            self.set_dirty(True)
            self.update_preview()
            return
        except IOError as e:
            print(f"Error saving image: {e}")
            QMessageBox.warning(self, "File Error", f"Failed to save image: {e}\n\nURL will be pasted as plain text.")
            self.editor.insert(url)
            self.set_dirty(True)
            self.update_preview()
            return
        except Exception as e:
            print(f"An unexpected error occurred while processing the image URL {url}: {e}")
            import traceback
            print(traceback.format_exc())
            QMessageBox.critical(self, "Unexpected Error", f"An unexpected error occurred while processing the image URL: {e}\n\nURL will be pasted as plain text.")
            self.editor.insert(url)
            self.set_dirty(True)
            self.update_preview()
            return

    def handle_pasted_plain_url(self, url: str):
        # For now, prompt for link text. AI part is a future enhancement.
        link_text_default = QUrl(url).host() or "Pasted Link" # Suggest domain or generic text
        link_text, ok = QInputDialog.getText(self, "Insert Link", "Enter link text:", 
                                            QLineEdit.EchoMode.Normal, link_text_default)
        if ok and link_text.strip():
            self.editor.insert(f"[{link_text.strip()}]({url})")
            self.set_dirty(True)
        else:
            # If user cancels or enters no text, insert the URL as is, not as a link.
            self.editor.insert(url)
            self.set_dirty(True)

    def load_last_note(self):
        """Loads the last opened note if its path is stored in the configuration."""
        config = load_app_config()
        last_note_path_str = config.get(CONFIG_KEY_LAST_NOTE)

        if last_note_path_str:
            # Normalize path from config before attempting to load
            normalized_path_str = self._normalize_path(last_note_path_str)
            if normalized_path_str: # Check if path is still valid after normalization
                last_note_path = Path(normalized_path_str)
                # Check if the file exists, is a file, and is a Markdown file
                if last_note_path.exists() and last_note_path.is_file() and \
                   last_note_path.suffix.lower() == '.md':
                    self.load_markdown_file(str(last_note_path))
                else:
                    # Optional: If the last note path is invalid/missing, clear it from config
                    # This prevents repeated attempts to load a non-existent file.
                    if CONFIG_KEY_LAST_NOTE in config:
                        del config[CONFIG_KEY_LAST_NOTE]
                        save_app_config(config)
                        print(f"Info: Last note '{normalized_path_str}' not found or invalid. Cleared from config.")

    def insert_link(self):
        """Inserts a Markdown link template at the current cursor position in the editor."""
        # Scintilla command to get current cursor position
        # pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        
        template = "[Link Text](https://example.com)"
        self.editor.insert(template) # Insert the template text
        
        # Optionally, move cursor to select "Link Text" or place it inside the URL parentheses
        # current_pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        # self.editor.SendScintilla(self.editor.SCI_SETSEL, current_pos - len(template) + 1, current_pos - len(template) + 1 + len("Link Text"))

    def insert_image(self):
        mode, ok = QInputDialog.getItem(self, "Insert Image", "Choose image source:", ["File", "URL"], 0, False)
        if not ok:
            return
        current_note_path = Path(self.current_file) if self.current_file else Path.cwd()
        assets_dir = current_note_path.parent / "_assets" / "images"
        assets_dir.mkdir(parents=True, exist_ok=True)
        if mode == "File":
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Image File", "", "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
            if not file_path:
                return
            width, ok_w = QInputDialog.getInt(self, "Image Width (optional)", "Width (px, 0 for original):", 0, 0)
            if not ok_w:
                return
            height, ok_h = QInputDialog.getInt(self, "Image Height (optional)", "Height (px, 0 for original):", 0, 0)
            if not ok_h:
                return
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}:
                ext = '.png'
            local_filepath = self._get_unique_asset_filename(assets_dir, ext)
            if width > 0 or height > 0:
                img = Image.open(file_path)
                orig_w, orig_h = img.size
                new_w = width if width > 0 else orig_w
                new_h = height if height > 0 else orig_h
                img = img.resize((new_w, new_h), Image.LANCZOS)
                img.save(local_filepath)
            else:
                shutil.copy2(file_path, local_filepath)
            rel_path = Path("_assets") / "images" / local_filepath.name
            if width > 0 or height > 0:
                html = f'<img src="{rel_path.as_posix()}" width="{width if width > 0 else ''}" height="{height if height > 0 else ''}" />'
                self.editor.insert(html)
            else:
                md = f'![image]({rel_path.as_posix()})'
                self.editor.insert(md)
        else:  # URL
            url, ok = QInputDialog.getText(self, "Insert Image URL", "Image URL:")
            if not ok or not url:
                return
            width, ok_w = QInputDialog.getInt(self, "Image Width (optional)", "Width (px, 0 for original):", 0, 0)
            if not ok_w:
                return
            height, ok_h = QInputDialog.getInt(self, "Image Height (optional)", "Height (px, 0 for original):", 0, 0)
            if not ok_h:
                return
            if url in MainWindow.failed_image_downloads:
                QMessageBox.warning(self, "Image Download Failed", f"Previously failed to download image from URL:\n{url}\nInserting as remote link.")
                if width > 0 or height > 0:
                    html = f'<img src="{url}" width="{width if width > 0 else ''}" height="{height if height > 0 else ''}" />'
                    self.editor.insert(html)
                else:
                    md = f'![image]({url})'
                    self.editor.insert(md)
                self.update_preview()
                return
            import urllib.parse
            url_path = urllib.parse.urlparse(url).path.lower()
            url_ext = os.path.splitext(url_path)[1]
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                content_type = resp.headers.get('Content-Type', '').lower().split(';')[0].strip()
                image_extensions_map = {
                    'image/jpeg': '.jpg', 'image/jpg': '.jpg',
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'image/webp': '.webp',
                    'image/svg+xml': '.svg',
                    'image/bmp': '.bmp'
                }
                if content_type in image_extensions_map:
                    ext = image_extensions_map[content_type]
                elif url_ext in image_extensions:
                    ext = url_ext
                else:
                    ext = '.png'
                local_filepath = self._get_unique_asset_filename(assets_dir, ext)
                with open(local_filepath, "wb") as f:
                    f.write(resp.content)
                rel_path = Path("_assets") / "images" / local_filepath.name
                success = True
            except Exception:
                try:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        "Referer": url,
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    }
                    resp = requests.get(url, headers=headers, timeout=10)
                    resp.raise_for_status()
                    content_type = resp.headers.get('Content-Type', '').lower().split(';')[0].strip()
                    if content_type in image_extensions_map:
                        ext = image_extensions_map[content_type]
                    elif url_ext in image_extensions:
                        ext = url_ext
                    else:
                        ext = '.png'
                    local_filepath = self._get_unique_asset_filename(assets_dir, ext)
                    with open(local_filepath, "wb") as f:
                        f.write(resp.content)
                    rel_path = Path("_assets") / "images" / local_filepath.name
                    success = True
                except Exception as e:
                    MainWindow.failed_image_downloads.add(url)
                    QMessageBox.warning(self, "Image Download Failed", f"Failed to download image from URL:\n{url}\nError: {e}\nInserting as remote link.")
                    if width > 0 or height > 0:
                        html = f'<img src="{url}" width="{width if width > 0 else ''}" height="{height if height > 0 else ''}" />'
                        self.editor.insert(html)
                    else:
                        md = f'![image]({url})'
                        self.editor.insert(md)
                    self.update_preview()
                    self.set_dirty(True)
                    return
            if width > 0 or height > 0:
                html = f'<img src="{rel_path.as_posix()}" width="{width if width > 0 else ''}" height="{height if height > 0 else ''}" />'
                self.editor.insert(html)
            else:
                md = f'![image]({rel_path.as_posix()})'
                self.editor.insert(md)
        self.update_preview()
        self.set_dirty(True)

    def update_preview(self):
        """Updates the Markdown preview pane with the current editor content."""
        if not self.current_file or not Path(self.current_file).is_file():
            self.preview.set_markdown("", base_url=QUrl())
            return
        text = self.editor.toPlainText()
        base_url = QUrl()
        try:
            file_path = Path(self.current_file)
            base_url = QUrl.fromLocalFile(str(file_path.parent.resolve()) + os.sep)
        except Exception as e:
            print(f"Error determining base_url for {self.current_file}: {e}")
        self.preview.set_markdown(text, base_url=base_url)

    def insert_table_of_contents(self):
        """Generate and insert a Table of Contents at the top of the document."""
        editor = getattr(self, 'editor', None)
        if not editor:
            QMessageBox.warning(self, "No Editor", "No editor instance found.")
            return
        markdown_text = editor.toPlainText()
        try:
            headings = extract_headings(markdown_text)
            toc_md = format_toc(headings)
        except Exception as e:
            QMessageBox.critical(self, "ToC Error", f"Failed to generate ToC: {e}")
            return
        if not toc_md:
            QMessageBox.information(self, "No Headings Found", "No headings found to generate a Table of Contents.")
            return
        # Insert ToC at the top
        new_text = f"<!-- TOC -->\n{toc_md}\n\n" + markdown_text
        editor.setPlainText(new_text)
        QMessageBox.information(self, "Table of Contents Inserted", "Table of Contents has been inserted at the top of the document.")

    def update_language_label(self):
        if getattr(self, 'language_override', None):
            self.language_label.setText(f"Language: {self.language_override} (manual)")
            return
        text = self.editor.toPlainText()
        try:
            lang = detect(text) if text.strip() else "unknown"
        except LangDetectException:
            lang = "unknown"
        self.language_label.setText(f"Language: {lang}")

    def set_language_override(self, value):
        value = value.strip()
        if value:
            self.language_override = value
            self.language_label.setText(f"Language: {value} (manual)")
        else:
            self.language_override = None
            self.update_language_label()

    def toggle_mode(self):
        if self.current_mode == 'preview':
            self.set_view_mode('edit')
        else:
            self.set_view_mode('preview')
        # Save last mode
        config = load_app_config()
        config[LAST_VIEW_MODE_KEY] = self.current_mode
        save_app_config(config)

    def toggle_sidebar(self):
        visible = not self.library_panel.isVisible()
        self.library_panel.setVisible(visible)
        self.toggle_sidebar_action.setChecked(visible)
        # Save sidebar visibility in config
        config = load_app_config()
        config['sidebar_visible'] = visible
        save_app_config(config)

    def handle_wiki_link(self, page_name):
        from pathlib import Path
        base = Path(self.default_folder)
        candidates = list(base.rglob(f"{page_name}.md"))
        if candidates:
            self.open_file(str(candidates[0]))
        else:
            from PyQt6.QtWidgets import QMessageBox
            resp = QMessageBox.question(self, "Create Page?", f"Page '{page_name}' does not exist. Create it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.Yes:
                new_path = base / f"{page_name}.md"
                with open(new_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {page_name}\n\n")
                self.open_file(str(new_path))

    # --- AI Feature Placeholders ---
    def ai_summarize_page(self):
        """Summarize the current markdown document using AI and show the result in a dialog with copy option."""
        if not self.ai:
            from config_utils import load_gemini_api_key
            api_key = load_gemini_api_key()
            if not api_key:
                QMessageBox.warning(self, "API Key Missing", "Gemini API key not found. Please set it in Preferences.")
                return
            self.ai = AIMarkdownAssistant(api_key)
        full_text = self.editor.toPlainText()
        if not full_text.strip():
            QMessageBox.information(self, "AI Summarize", "The document is empty.")
            return
        self.statusBar().showMessage("AI is summarizing the page...", 3000)
        try:
            summary = self.ai.summarize_document(full_text)
            if summary and not summary.startswith("Error:"):
                # Custom dialog with copy button
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Page Summary")
                msg_box.setText(summary)
                copy_btn = msg_box.addButton("Copy to Clipboard", QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton(QMessageBox.StandardButton.Ok)
                msg_box.exec()
                if msg_box.clickedButton() == copy_btn:
                    QApplication.clipboard().setText(summary)
                    self.statusBar().showMessage("Summary copied to clipboard.", 3000)
            else:
                QMessageBox.critical(self, "AI Summarize Failed", f"Could not generate summary. AI response:\n{summary}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "AI Error", f"An unexpected error occurred: {e}")
        self.statusBar().showMessage("AI summarization complete.", 3000)

    def ai_autolink_page(self):
        """Auto-link relevant terms in the current document to other notes using AI, with preview and copy option."""
        if not self.ai:
            from config_utils import load_gemini_api_key
            api_key = load_gemini_api_key()
            if not api_key:
                QMessageBox.warning(self, "API Key Missing", "Gemini API key not found. Please set it in Preferences.")
                return
            self.ai = AIMarkdownAssistant(api_key)
        full_text = self.editor.toPlainText()
        if not full_text.strip():
            QMessageBox.information(self, "AI Auto-Link", "The document is empty.")
            return
        # Gather all note titles (filenames without extension, excluding current file)
        from pathlib import Path
        base_path = Path(self.default_folder)
        note_titles = []
        for md_file in base_path.rglob('*.md'):
            if str(md_file.resolve()) != str(self.current_file):
                note_titles.append(md_file.stem)
        print(f"[DEBUG] Note titles for auto-linking: {note_titles}")
        if not note_titles:
            QMessageBox.information(self, "AI Auto-Link", "No other notes found to link to.")
            return
        self.statusBar().showMessage("AI is auto-linking the page...", 3000)
        try:
            linked_markdown = self.ai.auto_link_document(full_text, note_titles)
            if linked_markdown and not linked_markdown.startswith("Error:"):
                # Preview dialog with accept/cancel/copy
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Auto-Link Preview")
                msg_box.setText("AI-suggested auto-linking complete. Review the changes below.\n\n" + linked_markdown[:2000] + ("..." if len(linked_markdown) > 2000 else ""))
                accept_btn = msg_box.addButton("Accept Changes", QMessageBox.ButtonRole.AcceptRole)
                copy_btn = msg_box.addButton("Copy to Clipboard", QMessageBox.ButtonRole.ActionRole)
                cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)
                msg_box.exec()
                if msg_box.clickedButton() == accept_btn:
                    self.editor.setPlainText(linked_markdown)
                    self.set_dirty(True)
                    self.statusBar().showMessage("Auto-linking applied.", 3000)
                elif msg_box.clickedButton() == copy_btn:
                    QApplication.clipboard().setText(linked_markdown)
                    self.statusBar().showMessage("Auto-linked markdown copied to clipboard.", 3000)
                else:
                    self.statusBar().showMessage("Auto-linking cancelled.", 3000)
            else:
                QMessageBox.critical(self, "AI Auto-Link Failed", f"Could not auto-link. AI response:\n{linked_markdown}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "AI Error", f"An unexpected error occurred: {e}")
        self.statusBar().showMessage("AI auto-linking complete.", 3000)

    def ai_find_related_pages(self):
        QMessageBox.information(self, "AI Related Pages", "[Stub] Related pages feature coming soon.")

    def ai_semantic_search(self):
        QMessageBox.information(self, "AI Semantic Search", "[Stub] Semantic search feature coming soon.")

if __name__ == "__main__":
    # Standard PyQt application setup
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show() # Display the main window
    sys.exit(app.exec()) # Start the Qt event loop
