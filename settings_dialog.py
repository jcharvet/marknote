from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, 
    QPushButton, QFontComboBox, QSpinBox, QFileDialog, QDialogButtonBox, QMessageBox
)
from PyQt6.QtGui import QFont

from config_utils import (
    load_app_config, save_app_config,
    CONFIG_KEY_GEMINI_API_KEY,
    CONFIG_KEY_DEFAULT_NOTES_FOLDER,
    CONFIG_KEY_EDITOR_FONT_FAMILY,
    CONFIG_KEY_EDITOR_FONT_SIZE
)

class SettingsDialog(QDialog):
    """Dialog for managing application settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(500)

        self.config = load_app_config()

        # Main layout
        layout = QVBoxLayout(self)

        # Form layout for settings
        form_layout = QFormLayout()

        # Gemini API Key
        self.api_key_edit = QLineEdit()
        form_layout.addRow(QLabel("Gemini API Key:"), self.api_key_edit)

        # Default Notes Folder
        folder_layout = QHBoxLayout()
        self.notes_folder_edit = QLineEdit()
        self.notes_folder_edit.setReadOnly(True)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_default_folder)
        folder_layout.addWidget(self.notes_folder_edit)
        folder_layout.addWidget(browse_button)
        form_layout.addRow(QLabel("Default Notes Folder:"), folder_layout)

        # Editor Font Family
        self.font_family_combo = QFontComboBox()
        form_layout.addRow(QLabel("Editor Font Family:"), self.font_family_combo)

        # Editor Font Size
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setMinimum(8)
        self.font_size_spinbox.setMaximum(72)
        form_layout.addRow(QLabel("Editor Font Size:"), self.font_size_spinbox)

        layout.addLayout(form_layout)

        # Dialog buttons (OK, Cancel)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._load_settings()

    def _load_settings(self):
        """Loads current settings into the UI elements."""
        self.api_key_edit.setText(self.config.get(CONFIG_KEY_GEMINI_API_KEY, ""))
        self.notes_folder_edit.setText(self.config.get(CONFIG_KEY_DEFAULT_NOTES_FOLDER, ""))
        
        default_font_family = self.config.get(CONFIG_KEY_EDITOR_FONT_FAMILY, "Arial")
        self.font_family_combo.setCurrentFont(QFont(default_font_family))
        
        default_font_size = self.config.get(CONFIG_KEY_EDITOR_FONT_SIZE, 12)
        self.font_size_spinbox.setValue(default_font_size)

    def _save_settings(self) -> bool:
        """Saves the current UI settings to the configuration file."""
        self.config[CONFIG_KEY_GEMINI_API_KEY] = self.api_key_edit.text().strip()
        self.config[CONFIG_KEY_DEFAULT_NOTES_FOLDER] = self.notes_folder_edit.text().strip()
        self.config[CONFIG_KEY_EDITOR_FONT_FAMILY] = self.font_family_combo.currentFont().family()
        self.config[CONFIG_KEY_EDITOR_FONT_SIZE] = self.font_size_spinbox.value()

        if save_app_config(self.config):
            return True
        else:
            QMessageBox.warning(self, "Save Error", "Could not save settings to the configuration file.")
            return False

    def _browse_default_folder(self):
        """Opens a dialog to select the default notes folder."""
        current_path = self.notes_folder_edit.text()
        if not current_path:
            current_path = str(Path.home())
        
        folder_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Default Notes Folder", 
            current_path
        )
        if folder_path:
            self.notes_folder_edit.setText(folder_path)

    def accept(self):
        """Handles the OK button click, saving settings before closing."""
        if self._save_settings():
            super().accept()

    @staticmethod
    def get_settings(parent=None):
        """Static method to create, show dialog, and return True if accepted."""
        dialog = SettingsDialog(parent)
        return dialog.exec() == QDialog.DialogCode.Accepted

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    # Example of how to use the dialog
    if SettingsDialog.get_settings():
        print("Settings saved.")
    else:
        print("Settings dialog cancelled.")
    # To see changes, you'd typically reload config in the main app
    # For testing, print the current config
    print("Current config:", load_app_config())
