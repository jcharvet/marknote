import sys
import os
import json
from pathlib import Path
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
    MENUBAR_STYLESHEET = """
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
    """

    def __init__(self):
        super().__init__()
        self.default_folder = self.get_or_create_default_folder()
        self.setWindowTitle("Marknote - Markdown Editor with AI")
        self.resize(1100, 700)
        self.current_file = None
        self.last_saved_text = ""
        self.init_ui()
        self.load_last_note()
        self.load_recent_files()

    def command_bar_key_press_event(self, event):
        from PyQt6.QtGui import QKeyEvent
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.execute_command()
        else:
            QTextEdit.keyPressEvent(self.command_bar, event)

    def closeEvent(self, event):
        # Prompt to save on close
        if not self.maybe_save_changes():
            event.ignore()
        else:
            if self.current_file and self.current_file.endswith('.md'):
                self.save_last_note(self.current_file)
                self.add_to_recent_files(self.current_file)
            event.accept()

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

        export_as_action = QAction("Export As...", self)
        export_as_action.triggered.connect(self.export_file_as)
        file_menu.addAction(export_as_action)

        print_action = QAction("Print...", self)
        print_action.triggered.connect(self.print_file)
        # You might want to add a shortcut like Ctrl+P here later
        file_menu.addAction(print_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close_application) # Or self.close directly
        file_menu.addAction(exit_action)

        # Other Menu
        other_menu = menubar.addMenu("Other")

        link_action = QAction("Link", self)
        link_action.triggered.connect(self.insert_link)
        other_menu.addAction(link_action)

        ai_command_action = QAction("AI Command", self)
        ai_command_action.setShortcut(QKeySequence("Ctrl+Shift+Space"))
        ai_command_action.triggered.connect(self.show_command_bar)
        other_menu.addAction(ai_command_action)

        # Help Menu
        help_menu = menubar.addMenu("Help")
        syntax_action = QAction("Markdown & Mermaid Syntax", self) # This maps to "Help feature"
        syntax_action.triggered.connect(self.show_syntax_help)
        help_menu.addAction(syntax_action)

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
        self.library.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library.customContextMenuRequested.connect(self.show_library_context_menu)
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

    def open_file(self, file_path=None):
        if not self.maybe_save_changes():
            return
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "Open Markdown File", "docs", "Markdown Files (*.md);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.editor.setPlainText(content)
                self.current_file = file_path
                self.last_saved_text = content
                self.setWindowTitle(f"Marknote - {os.path.basename(file_path)}")
                self.preview.set_markdown(content)
                self.add_to_recent_files(file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file: {e}")

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder", str(self.default_folder))
        if folder:
            self.default_folder = folder
            # Persist the new default folder to config.json
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            try:
                config = {}
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                config['DEFAULT_FOLDER'] = folder
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
            except Exception as e:
                QMessageBox.warning(self, "Config Error", f"Could not save default folder to config.json:\n{e}")
            self.refresh_library()

    def open_tree_item(self, item, column):
        import os
        path = item.data(0, 1)
        if os.path.isdir(path):
            # Toggle expand/collapse
            if item.isExpanded():
                self.library.collapseItem(item)
            else:
                self.library.expandItem(item)
            # Always clear and set editor to read-only with a message
            if not self.maybe_save_changes():
                return
            self.editor.setReadOnly(True)
            self.editor.setPlainText("Select a file to edit or create a new file in this folder.")
            self.preview.set_markdown("")
            self.current_file = None
            self.last_saved_text = ""
        elif path.endswith(".md"):
            if not self.maybe_save_changes():
                return
            self.load_markdown_file(path)
            self.editor.setReadOnly(False)

    def load_markdown_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                self.editor.setPlainText(content)
                self.last_saved_text = content
                self.current_file = path
                self.save_last_note(path)
            self.preview.set_markdown(self.editor.toPlainText())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file: {e}")

    def save_file(self):
        text = self.editor.toPlainText()
        if self.current_file:
            try:
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(text)
                self.last_saved_text = text
                self.setWindowTitle(f"Marknote - {os.path.basename(self.current_file)}")
                self.add_to_recent_files(self.current_file)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
        else:
            self.save_file_as()

    def save_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Markdown File As", "docs", "Markdown Files (*.md);;All Files (*)")
        if file_path:
            if not file_path.endswith('.md'):
                file_path += '.md'
            self.current_file = file_path
            self.save_file()
            # self.add_to_recent_files(file_path) # save_file already does this

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
        if not self.maybe_save_changes():
            return
        folder_name, ok = QInputDialog.getText(self, "Create Folder", "Folder name:")
        if ok and folder_name.strip():
            base_dir = self.default_folder
            new_folder_path = os.path.join(base_dir, folder_name.strip())
            try:
                os.makedirs(new_folder_path, exist_ok=True)
                # Create a default.md file in the new folder
                default_file_path = os.path.join(new_folder_path, "default.md")
                with open(default_file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                self.refresh_library(self.search_bar.text())
                self.load_markdown_file(default_file_path)
                self.editor.setReadOnly(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create folder: {e}")

    def new_file(self):
        if self.maybe_save_changes():
            self.editor.clear()
            self.current_file = None
            self.last_saved_text = ""
            self.setWindowTitle("Marknote - Untitled")
            self.preview.set_markdown("")
            # Do not add None or "Untitled" to recent files here

    def maybe_save_changes(self):
        """
        Returns True to continue, False to abort navigation or close.
        """
        if self.editor.isReadOnly():
            return True
        text = self.editor.toPlainText()
        if text != self.last_saved_text:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_file()
                # If still unsaved (user canceled in save dialog), abort
                if self.editor.toPlainText() != self.last_saved_text:
                    return False
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        return True

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

    def show_library_context_menu(self, position):
        item = self.library.itemAt(position)
        if not item:
            return
        import os
        path = item.data(0, 1)
        menu = QMenu(self)
        if os.path.isdir(path):
            new_file_action = menu.addAction("New File")
            rename_action = menu.addAction("Rename Folder")
            # Always allow delete action, but warn if not empty
            import os
            is_empty = not any(os.scandir(path))
            delete_action = menu.addAction("Delete Folder")
            new_file_action.triggered.connect(lambda: self.create_file_in_folder(path))
            delete_action.triggered.connect(lambda: self.delete_file_or_folder(item, path, is_folder=True))
            rename_action.triggered.connect(lambda: self.rename_file_or_folder(item, path, is_folder=True))
        else:
            rename_action = menu.addAction("Rename File")
            delete_action = menu.addAction("Delete File")
            rename_action.triggered.connect(lambda: self.rename_file_or_folder(item, path, is_folder=False))
            delete_action.triggered.connect(lambda: self.delete_file_or_folder(item, path, is_folder=False))
        menu.exec(self.library.viewport().mapToGlobal(position))

    def rename_file_or_folder(self, item, path, is_folder):
        import os
        base_dir = os.path.dirname(path) if not is_folder else os.path.dirname(path.rstrip(os.sep))
        old_name = os.path.basename(path.rstrip(os.sep)) if is_folder else os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, "Rename", f"Enter new name for {'folder' if is_folder else 'file'}:", text=old_name)
        if ok and new_name.strip():
            new_path = os.path.join(base_dir, new_name.strip())
            try:
                os.rename(path, new_path)
                self.refresh_library(self.search_bar.text())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename: {e}")

    def create_file_in_folder(self, folder_path):
        import os
        if not self.maybe_save_changes():
            return
        file_name, ok = QInputDialog.getText(self, "New File", "Enter new file name (with .md extension):")
        if ok and file_name.strip():
            if not file_name.strip().endswith('.md'):
                file_name = file_name.strip() + '.md'
            new_file_path = os.path.join(folder_path, file_name)
            if os.path.exists(new_file_path):
                QMessageBox.warning(self, "File Exists", f"A file named '{file_name}' already exists in this folder.")
                return
            try:
                with open(new_file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                self.refresh_library(self.search_bar.text())
                self.load_markdown_file(new_file_path)
                self.editor.setReadOnly(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create file: {e}")

    def delete_file_or_folder(self, item, path, is_folder):
        if is_folder:
            # Always show warning if folder is not empty
            if any(os.scandir(path)):
                QMessageBox.warning(
                    self,
                    "Cannot Delete Folder",
                    f"This folder cannot be deleted because it is not empty.\n\nTo delete a folder, first remove all files and subfolders inside it.\n(This is the same as Unix behavior: rmdir only works on empty folders.)"
                )
                return
            msg = f"Are you sure you want to delete this folder?\n{path}"
        else:
            msg = f"Are you sure you want to delete this file?\n{path}"
        reply = QMessageBox.question(self, "Delete", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if is_folder:
                    os.rmdir(path)
                else:
                    os.remove(path)
                # UX improvement: If the current file is deleted, clear editor/preview
                if not is_folder and self.current_file == path:
                    self.editor.clear()
                    self.preview.set_markdown("")
                    self.current_file = None
                    self.last_saved_text = ""
                elif is_folder and self.current_file and self.current_file.startswith(path + os.sep):
                    # If current file is inside the deleted folder
                    self.editor.clear()
                    self.preview.set_markdown("")
                    self.current_file = None
                    self.last_saved_text = ""
                self.refresh_library(self.search_bar.text())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

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

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        if not hasattr(self, 'recent_files_list') or not self.recent_files_list:
            no_recent_action = QAction("(No recent files)", self)
            no_recent_action.setEnabled(False)
            self.recent_files_menu.addAction(no_recent_action)
            return

        for file_path in self.recent_files_list:
            action = QAction(os.path.basename(file_path), self)
            action.setData(file_path)
            action.triggered.connect(self.open_recent_file_action)
            self.recent_files_menu.addAction(action)

    def open_recent_file_action(self):
        action = self.sender()
        if action:
            file_path = action.data()
            if file_path:
                self.open_file(file_path)

    MAX_RECENT_FILES = 10
    RECENT_FILES_PATH = Path.home() / '.marknote_recent_files.json'

    def load_recent_files(self):
        if self.RECENT_FILES_PATH.exists():
            try:
                with open(self.RECENT_FILES_PATH, 'r') as f:
                    self.recent_files_list = json.load(f)
            except (IOError, json.JSONDecodeError):
                self.recent_files_list = []
        else:
            self.recent_files_list = []
        self.update_recent_files_menu()

    def save_recent_files(self):
        try:
            with open(self.RECENT_FILES_PATH, 'w') as f:
                json.dump(self.recent_files_list, f)
        except IOError:
            # Handle error (e.g., log it) if necessary
            pass

    def add_to_recent_files(self, file_path):
        if not file_path: # Do not add None or empty paths
            return
        if file_path in self.recent_files_list:
            self.recent_files_list.remove(file_path)
        self.recent_files_list.insert(0, file_path)
        self.recent_files_list = self.recent_files_list[:self.MAX_RECENT_FILES]
        self.save_recent_files()
        self.update_recent_files_menu()

    def export_file_as(self):
        if not self.editor.toPlainText():
            QMessageBox.information(self, "Export As", "There is no content to export.")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export File As",
            self.default_folder, # Or derive a filename from current_file
            "HTML Document (*.html);;Plain Text (*.txt)"
        )

        if not file_path:
            return # User cancelled

        content_to_save = ""
        current_markdown_text = self.editor.toPlainText()

        try:
            if selected_filter == "HTML Document (*.html)":
                if not file_path.lower().endswith('.html'):
                    file_path += '.html'
                # Basic HTML conversion, similar to preview but without live mermaid script
                # For a standalone HTML, we might want to embed styles or provide a full HTML structure
                html_content = markdown.markdown(current_markdown_text, extensions=['fenced_code'])
                # Simple HTML wrapper
                content_to_save = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <title>Exported Markdown</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; line-height: 1.6; }}
        code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 3px; overflow-x: auto; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
            elif selected_filter == "Plain Text (*.txt)":
                if not file_path.lower().endswith('.txt'):
                    file_path += '.txt'
                content_to_save = current_markdown_text
            else:
                # Should not happen if filters are set correctly
                QMessageBox.warning(self, "Export Error", "Invalid file type selected.")
                return

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_to_save)
            QMessageBox.information(self, "Export Successful", f"File exported successfully to {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not export file: {e}")

    def close_application(self):
        self.close() # This will trigger the closeEvent

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

    def _normalize_path(self, path):
        # On Linux, ignore Windows drive-letter paths or backslashes
        if sys.platform != "win32":
            if path and ("\\" in path or (len(path) > 2 and path[1] == ':' and path[2] in ['\\', '/'])):
                # Path is Windows-style, ignore/reset
                return str(Path.home() / 'Documents' / 'Marknote')
        # Normalize path for current OS
        return os.path.abspath(os.path.normpath(path)) if path else str(Path.home() / 'Documents' / 'Marknote')

    def get_or_create_default_folder(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        config = {}
        default_folder = None
        # Single config read
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    default_folder = config.get('DEFAULT_FOLDER')
        except Exception as e:
            QMessageBox.warning(None, "Config Error", f"Could not read config.json:\n{e}")
        # Normalize and validate path
        default_folder = self._normalize_path(default_folder)
        # If default_folder is set and exists, just use it (create if missing)
        if default_folder and isinstance(default_folder, str):
            folder_path = Path(default_folder)
            if not folder_path.exists():
                try:
                    folder_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    QMessageBox.warning(None, "Config Error", f"Could not create default folder: {e}")
            # Save config (single write)
            try:
                config['DEFAULT_FOLDER'] = str(folder_path)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
            except Exception as e:
                QMessageBox.warning(None, "Config Error", f"Could not save default folder to config.json:\n{e}")
            return str(folder_path)
        # Otherwise prompt the user
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
        # Normalize again
        default_folder = self._normalize_path(default_folder)
        # Save config (single write)
        try:
            config['DEFAULT_FOLDER'] = default_folder
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            QMessageBox.warning(None, "Config Error", f"Could not save default folder to config.json:\n{e}")
        # Create folder if it doesn't exist
        os.makedirs(default_folder, exist_ok=True)
        return default_folder

    def save_last_note(self, path):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            # Normalize path before saving
            path = self._normalize_path(path)
            config['LAST_NOTE'] = path
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Config Error", f"Could not save last note to config.json:\n{e}")

    def load_last_note(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    last_note = config.get('LAST_NOTE')
                    last_note = self._normalize_path(last_note)
                    if last_note and os.path.exists(last_note) and last_note.endswith('.md'):
                        self.load_markdown_file(last_note)
        except Exception as e:
            QMessageBox.warning(self, "Config Error", f"Could not load last note from config.json:\n{e}")

    def print_file(self):
        # Placeholder: Implement printing functionality
        QMessageBox.information(self, "Print", "Print functionality not yet implemented.")

    def insert_link(self):
        # Insert a Markdown link template at the cursor
        cursor = self.editor.SendScintilla
        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        template = "[Link Text](https://example.com)"
        self.editor.insert(template)
        # Optionally, move cursor between brackets

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
