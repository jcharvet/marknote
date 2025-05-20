import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QToolBar, QMessageBox, QMenu, QLineEdit, QTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem, QPushButton, QInputDialog
)
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
from PyQt6.QtCore import Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.Qsci import QsciScintilla, QsciLexerMarkdown
import markdown
import re
from ai import AIMarkdownAssistant

class MarkdownEditor(QsciScintilla):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Set lexer for Markdown
        lexer = QsciLexerMarkdown()
        lexer.setDefaultFont(QFont("Fira Mono", 12))
        lexer.setFont(QFont("Fira Mono", 12))
        # Set colors for dark mode
        lexer.setColor(QColor("#d7dae0"))
        lexer.setPaper(QColor("#282c34"))
        self.setLexer(lexer)
        self.setUtf8(True)
        self.setMarginsBackgroundColor(QColor("#21252b"))
        self.setMarginsForegroundColor(QColor("#61AFEF"))
        self.setCaretForegroundColor(QColor("#61AFEF"))
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setAutoIndent(True)
        self.setIndentationGuides(True)
        self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
        self.setTabWidth(4)
        self.setIndentationsUseTabs(False)
        self.setFont(QFont("Fira Mono", 12))
        self.setStyleSheet("background-color: #282c34; color: #d7dae0;")

    def toPlainText(self):
        return self.text()

    def setPlainText(self, text):
        self.setText(text)

    def clear(self):
        self.setText("")

class MarkdownPreview(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #21252b; color: #d7dae0; font-family: sans-serif;")

    def set_markdown(self, text):
        # Detect ```mermaid code blocks in raw Markdown
        def mermaid_replacer(match):
            code = match.group(1)
            return f'<div class="mermaid">{code}</div>'
        # Replace all ```mermaid ... ``` blocks
        mermaid_pattern = re.compile(r'```mermaid\s*([\s\S]*?)```', re.MULTILINE)
        text_with_mermaid = mermaid_pattern.sub(mermaid_replacer, text)
        # Convert to HTML
        html = markdown.markdown(text_with_mermaid, extensions=['fenced_code'])
        # If any mermaid blocks, inject Mermaid.js
        if '<div class="mermaid">' in html:
            html = f'''
            <html>
            <head>
                <style>body {{ background: #21252b; color: #d7dae0; }}</style>
                <script type="module">
                  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                  mermaid.initialize({{ startOnLoad: true }});
                </script>
            </head>
            <body>{html}</body>
            </html>
            '''
        else:
            html = f'''<html><head><style>body {{ background: #21252b; color: #d7dae0; }}</style></head><body>{html}</body></html>'''
        self.setHtml(html)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.default_folder = self.get_or_create_default_folder()
        self.setWindowTitle("Marknote - Markdown Editor with AI")
        self.resize(1100, 700)
        self.init_ui()

    def command_bar_key_press_event(self, event):
        from PyQt6.QtGui import QKeyEvent
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.execute_command()
        else:
            QTextEdit.keyPressEvent(self.command_bar, event)


    def init_ui(self):
        # Set dark palette
        # Inform the user of the default folder at startup
        QMessageBox.information(self, "Default Folder", f"Using folder: {self.default_folder}")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#282c34"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#d7dae0"))
        self.setPalette(palette)

        # Menu bar with Help
        menubar = self.menuBar()
        help_menu = menubar.addMenu("Help")
        syntax_action = QAction("Markdown & Mermaid Syntax", self)
        syntax_action.triggered.connect(self.show_syntax_help)
        help_menu.addAction(syntax_action)

        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        toolbar.setStyleSheet("background: #21252b; color: #61AFEF;")
        self.addToolBar(toolbar)

        open_action = QAction(QIcon(), "Open", self)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)

        save_action = QAction(QIcon(), "Save", self)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)

        new_action = QAction(QIcon(), "New", self)
        new_action.triggered.connect(self.new_file)
        toolbar.addAction(new_action)

        link_action = QAction(QIcon(), "Link", self)
        link_action.triggered.connect(self.insert_link)
        toolbar.addAction(link_action)

        # AI Command Bar button
        ai_command_action = QAction(QIcon(), "AI Command", self)
        ai_command_action.setToolTip("Open AI Command Bar (Ctrl+Shift+Space)")
        ai_command_action.triggered.connect(self.show_command_bar)
        toolbar.addAction(ai_command_action)

        # Document library area
        library_panel = QWidget()
        library_layout = QVBoxLayout()
        library_layout.setContentsMargins(0,0,0,0)
        library_panel.setLayout(library_layout)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search documents...")
        self.search_bar.textChanged.connect(self.filter_library)
        library_layout.addWidget(self.search_bar)

        # New Folder button
        self.folder_btn = QPushButton("New Folder")
        self.folder_btn.clicked.connect(self.create_folder)
        self.folder_btn.setStyleSheet("background: #282c34; color: #98c379; border: none; padding: 5px;")
        library_layout.addWidget(self.folder_btn)

        # QTreeWidget for files/folders
        self.library = QTreeWidget()
        self.library.setHeaderHidden(True)
        self.library.setStyleSheet("background: #23252b; color: #61AFEF; font-size: 13px;")
        self.library.setMaximumWidth(210)
        self.library.itemClicked.connect(self.open_tree_item)
        library_layout.addWidget(self.library)
        self.refresh_library()

        # Editor and preview
        self.editor = MarkdownEditor()
        self.preview = MarkdownPreview()
        self.editor.textChanged.connect(self.update_preview)

        # Use QSplitter for resizable panels
        splitter = QSplitter()
        splitter.addWidget(library_panel)
        editor_preview = QWidget()
        ep_layout = QHBoxLayout()
        ep_layout.setContentsMargins(0,0,0,0)
        editor_preview.setLayout(ep_layout)
        ep_layout.addWidget(self.editor, 2)
        ep_layout.addWidget(self.preview, 2)
        splitter.addWidget(editor_preview)
        splitter.setSizes([210, 950])

        # Set up central widget and layout
        central = QWidget()
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(0,0,0,0)
        central.setLayout(central_layout)
        self.setCentralWidget(central)
        central_layout.addWidget(splitter)

        # AI assistant
        self.ai = AIMarkdownAssistant()

        # Context menu integration
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)

        # AI command bar (multi-line)
        self.command_bar_widget = QWidget(self)
        from PyQt6.QtWidgets import QHBoxLayout as QHBoxLayoutWidget
        self.command_bar_layout = QHBoxLayoutWidget()
        self.command_bar_widget.setLayout(self.command_bar_layout)
        self.command_bar = QTextEdit(self)
        self.command_bar.setPlaceholderText("AI Command (Ctrl+Enter to send)")
        self.command_bar.setFixedHeight(60)
        self.command_bar.hide()
        self.send_button = QPushButton("Send", self)
        self.send_button.clicked.connect(self.execute_command)
        self.command_bar_layout.addWidget(self.command_bar)
        self.command_bar_layout.addWidget(self.send_button)
        self.command_bar_widget.hide()
        # Add AI command bar to the central layout after splitter
        self.centralWidget().layout().addWidget(self.command_bar_widget)
        self.command_shortcut = QAction(self)
        self.command_shortcut.setShortcut(QKeySequence("Ctrl+Shift+Space"))
        self.command_shortcut.triggered.connect(self.show_command_bar)
        self.addAction(self.command_shortcut)
        self.command_bar.keyPressEvent = self.command_bar_key_press_event

        self.update_preview()

    def update_preview(self):
        text = self.editor.toPlainText()
        self.preview.set_markdown(text)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Markdown File", "docs", "Markdown Files (*.md);;All Files (*)")
        if path:
            self.load_markdown_file(path)

    def open_tree_item(self, item, column):
        import os
        path = item.data(0, 1)
        if os.path.isdir(path):
            # Toggle expand/collapse
            if item.isExpanded():
                self.library.collapseItem(item)
            else:
                self.library.expandItem(item)
        elif path.endswith(".md"):
            self.load_markdown_file(path)

    def load_markdown_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())
            self.preview.set_markdown(self.editor.toPlainText())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file: {e}")


    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Markdown File", "docs", "Markdown Files (*.md);;All Files (*)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self.refresh_library(self.search_bar.text())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def refresh_library(self, filter_text=""):
        import os
        from pathlib import Path
        self.library.clear()
        base_dir = self.default_folder
        def add_items(parent, path):
            try:
                entries = sorted(Path(path).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for entry in entries:
                    if entry.is_dir():
                        folder_item = QTreeWidgetItem([entry.name])
                        folder_item.setData(0, 1, str(entry))
                        parent.addChild(folder_item)
                        add_items(folder_item, entry)
                    elif entry.suffix.lower() == ".md":
                        if filter_text.lower() in entry.name.lower():
                            file_item = QTreeWidgetItem([entry.name])
                            file_item.setData(0, 1, str(entry))
                            parent.addChild(file_item)
            except Exception as e:
                pass
        root = QTreeWidgetItem(["docs"])
        root.setData(0, 1, base_dir)
        add_items(root, base_dir)
        self.library.addTopLevelItem(root)
        self.library.expandAll()

    def filter_library(self, text):
        self.refresh_library(filter_text=text)

    def create_folder(self):
        import os
        folder_name, ok = QInputDialog.getText(self, "Create Folder", "Folder name:")
        if ok and folder_name.strip():
            base_dir = self.default_folder
            new_folder_path = os.path.join(base_dir, folder_name.strip())
            try:
                os.makedirs(new_folder_path, exist_ok=True)
                self.refresh_library(self.search_bar.text())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create folder: {e}")


    def new_file(self):
        self.editor.clear()
        self.preview.set_markdown("")

    def get_or_create_default_folder(self):
        import os, json
        from pathlib import Path
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        default_folder = None
        config = {}
        # Try to read from config.json
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                default_folder = config.get('DEFAULT_FOLDER')
        except Exception:
            pass
        # If not set, prompt the user
        if not default_folder:
            user_choice = QMessageBox.question(None, "Default Folder", "No default folder is set.\nWould you like to use the system default (~/Documents/Marknote)?",
                                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if user_choice == QMessageBox.StandardButton.Yes:
                default_folder = str(Path.home() / 'Documents' / 'Marknote')
            else:
                folder = QFileDialog.getExistingDirectory(None, "Select a folder for Marknote")
                if folder:
                    default_folder = folder
                else:
                    # fallback
                    default_folder = str(Path.home() / 'Documents' / 'Marknote')
            # Persist the user's choice
            try:
                config['DEFAULT_FOLDER'] = default_folder
                # Preserve other config keys (like GEMINI_API_KEY)
                if 'GEMINI_API_KEY' not in config:
                    # Try to preserve existing API key if present
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            old_config = json.load(f)
                            if 'GEMINI_API_KEY' in old_config:
                                config['GEMINI_API_KEY'] = old_config['GEMINI_API_KEY']
                    except Exception:
                        pass
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
            except Exception as e:
                QMessageBox.warning(None, "Config Error", f"Could not save default folder to config.json:\n{e}")
        # Create folder if it doesn't exist
        os.makedirs(default_folder, exist_ok=True)
        return default_folder



    def insert_link(self):
        # Insert a Markdown link template at the cursor
        cursor = self.editor.SendScintilla
        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        template = "[Link Text](https://example.com)"
        self.editor.insert(template)
        # Optionally, move cursor between brackets

    def show_context_menu(self, position):
        menu = QMenu(self)
        expand_action = menu.addAction("Expand with AI")
        refine_action = menu.addAction("Refine with AI")
        analyze_action = menu.addAction("Analyze Document")
        command_action = menu.addAction("AI Command Bar")
        nlp_command_action = menu.addAction("AI Command (Natural Language)")
        expand_action.triggered.connect(self.expand_selected_text)
        refine_action.triggered.connect(self.refine_selected_text)
        analyze_action.triggered.connect(self.analyze_document)
        command_action.triggered.connect(self.show_command_bar)
        nlp_command_action.triggered.connect(self.show_command_bar)
        menu.exec(self.editor.mapToGlobal(position))

    def expand_selected_text(self):
        selected = self.editor.selectedText()
        if selected:
            expanded = self.ai.expand_content(selected)
            self.editor.replaceSelectedText(expanded)

    def refine_selected_text(self):
        selected = self.editor.selectedText()
        if selected:
            refined = self.ai.refine_writing(selected)
            self.editor.replaceSelectedText(refined)

    def analyze_document(self):
        text = self.editor.text()
        analysis = self.ai.analyze_document(text)
        QMessageBox.information(self, "AI Document Analysis", analysis)

    def show_command_bar(self):
        self.command_bar_widget.show()
        self.command_bar.show()
        self.command_bar.setFocus()

    def execute_command(self):
        command = self.command_bar.toPlainText()
        self.command_bar.clear()
        self.command_bar_widget.hide()
        selected = self.editor.selectedText()
        result = self.ai.process_natural_command(command, selected_text=selected if selected else None)
        # Always append at the end of the document
        last_line = self.editor.lines() - 1
        last_line_text = self.editor.text(last_line)
        self.editor.setCursorPosition(last_line, len(last_line_text))
        # Add a newline if not already present
        if last_line_text.strip() != "":
            self.editor.insert("\n" + result)
        else:
            self.editor.insert(result)


    def show_syntax_help(self):
        help_text = (
            "<b>Markdown Syntax:</b><br>"
            "<ul>"
            "<li><b>Bold:</b> <code>**bold text**</code></li>"
            "<li><b>Italic:</b> <code>*italic text*</code></li>"
            "<li><b>Heading:</b> <code># Heading 1</code>, <code>## Heading 2</code></li>"
            "<li><b>List:</b> <code>- Item</code></li>"
            "<li><b>Link:</b> <code>[Link Text](https://example.com)</code></li>"
            "<li><b>Image:</b> <code>![Alt Text](image.png)</code></li>"
            "<li><b>Code:</b> <code>`inline code`</code> or <code>```python\ncode block\n```</code></li>"
            "</ul>"
            "<b>Mermaid Diagram:</b><br>"
            "<pre>```mermaid\ngraph TD\n  A[Start] --> B{Is it working?}\n  B -- Yes --> C[Great!]\n  B -- No --> D[Fix it]\n```</pre>"
            "<br>See <a href='https://mermaid-js.github.io/mermaid/#/'>Mermaid docs</a> for more.</br>"
        )
        QMessageBox.information(self, "Markdown & Mermaid Syntax", help_text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
