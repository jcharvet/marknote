from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, 
    QPushButton, QFontComboBox, QSpinBox, QFileDialog, QDialogButtonBox, QMessageBox, QRadioButton, QCheckBox
)
from PyQt6.QtGui import QFont

from config_utils import (
    load_app_config, save_app_config,
    CONFIG_KEY_GEMINI_API_KEY,
    CONFIG_KEY_DEFAULT_NOTES_FOLDER,
    CONFIG_KEY_EDITOR_FONT_FAMILY,
    CONFIG_KEY_EDITOR_FONT_SIZE,
    CONFIG_KEY_SIDEBAR_VISIBLE
)

DEFAULT_VIEW_MODE_KEY = "default_view_mode"
REMEMBER_LAST_MODE_KEY = "remember_last_view_mode"

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

        # --- View Mode Options ---
        view_mode_layout = QHBoxLayout()
        self.radio_preview = QRadioButton("Preview (HTML)")
        self.radio_edit = QRadioButton("Edit (Markdown)")
        view_mode_layout.addWidget(self.radio_preview)
        view_mode_layout.addWidget(self.radio_edit)
        form_layout.addRow(QLabel("Default View Mode:"), view_mode_layout)
        self.remember_last_mode_checkbox = QCheckBox("Remember last used mode")
        form_layout.addRow(QLabel(""), self.remember_last_mode_checkbox)

        # Sidebar visibility
        self.sidebar_visible_checkbox = QCheckBox("Show sidebar by default")
        form_layout.addRow(QLabel(""), self.sidebar_visible_checkbox)

        # Auto-Save
        self.autosave_checkbox = QCheckBox("Enable Auto-Save")
        self.autosave_interval_spinbox = QSpinBox()
        self.autosave_interval_spinbox.setMinimum(5)
        self.autosave_interval_spinbox.setMaximum(3600)
        self.autosave_interval_spinbox.setSuffix(" s")
        autosave_layout = QHBoxLayout()
        autosave_layout.addWidget(self.autosave_checkbox)
        autosave_layout.addWidget(QLabel("Interval:"))
        autosave_layout.addWidget(self.autosave_interval_spinbox)
        form_layout.addRow(QLabel("Auto-Save:"), autosave_layout)

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

        # View mode
        default_mode = self.config.get(DEFAULT_VIEW_MODE_KEY, "preview")
        if default_mode == "edit":
            self.radio_edit.setChecked(True)
        else:
            self.radio_preview.setChecked(True)
        self.remember_last_mode_checkbox.setChecked(self.config.get(REMEMBER_LAST_MODE_KEY, True))
        self.sidebar_visible_checkbox.setChecked(self.config.get(CONFIG_KEY_SIDEBAR_VISIBLE, True))

        # Auto-Save
        self.autosave_checkbox.setChecked(self.config.get("autosave_enabled", True))
        self.autosave_interval_spinbox.setValue(self.config.get("autosave_interval", 60))

    def _save_settings(self) -> bool:
        """Saves the current UI settings to the configuration file."""
        self.config[CONFIG_KEY_GEMINI_API_KEY] = self.api_key_edit.text().strip()
        self.config[CONFIG_KEY_DEFAULT_NOTES_FOLDER] = self.notes_folder_edit.text().strip()
        self.config[CONFIG_KEY_EDITOR_FONT_FAMILY] = self.font_family_combo.currentFont().family()
        self.config[CONFIG_KEY_EDITOR_FONT_SIZE] = self.font_size_spinbox.value()
        # View mode
        self.config[DEFAULT_VIEW_MODE_KEY] = "edit" if self.radio_edit.isChecked() else "preview"
        self.config[REMEMBER_LAST_MODE_KEY] = self.remember_last_mode_checkbox.isChecked()
        self.config[CONFIG_KEY_SIDEBAR_VISIBLE] = self.sidebar_visible_checkbox.isChecked()

        # Auto-Save
        self.config["autosave_enabled"] = self.autosave_checkbox.isChecked()
        self.config["autosave_interval"] = self.autosave_interval_spinbox.value()

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
