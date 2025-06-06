from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox, QComboBox, QLineEdit, QRadioButton, QHBoxLayout, QSpinBox, QButtonGroup

class AIPromptDialog(QDialog):
    def __init__(self, prompt_label: str = "Enter your prompt:", parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Prompt")
        self.setMinimumWidth(500)
        self.setMinimumHeight(250)

        layout = QVBoxLayout(self)
        self.label = QLabel(prompt_label)
        layout.addWidget(self.label)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlaceholderText("Type your prompt here...")
        layout.addWidget(self.text_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_prompt(self) -> str:
        return self.text_edit.toPlainText().strip()

    @staticmethod
    def get_prompt_from_user(prompt_label: str = "Enter your prompt:", parent=None) -> tuple[str, bool]:
        dialog = AIPromptDialog(prompt_label, parent)
        result = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.get_prompt(), result

class AdvancedSummarizationDialog(QDialog):
    def __init__(self, has_selection: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Summarization")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        # Summary Length
        layout.addWidget(QLabel("Summary Length:"))
        self.length_combo = QComboBox()
        self.length_combo.addItems(["Short (1-2 sentences)", "Medium (3-5 sentences)", "Long (paragraph)", "Custom..."])
        layout.addWidget(self.length_combo)
        self.custom_length_box = QSpinBox()
        self.custom_length_box.setMinimum(1)
        self.custom_length_box.setMaximum(20)
        self.custom_length_box.setValue(5)
        self.custom_length_box.setVisible(False)
        layout.addWidget(self.custom_length_box)
        self.length_combo.currentIndexChanged.connect(self._on_length_changed)

        # Summary Style
        layout.addWidget(QLabel("Summary Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Paragraph", "Bullet Points"])
        layout.addWidget(self.style_combo)

        # Keywords
        layout.addWidget(QLabel("Keywords (optional, comma-separated):"))
        self.keywords_edit = QLineEdit()
        layout.addWidget(self.keywords_edit)

        # Target
        layout.addWidget(QLabel("Target:"))
        self.target_group = QButtonGroup(self)
        self.target_full = QRadioButton("Full Document")
        self.target_selection = QRadioButton("Selected Text")
        self.target_group.addButton(self.target_full)
        self.target_group.addButton(self.target_selection)
        self.target_full.setChecked(True)
        self.target_selection.setEnabled(has_selection)
        target_layout = QHBoxLayout()
        target_layout.addWidget(self.target_full)
        target_layout.addWidget(self.target_selection)
        layout.addLayout(target_layout)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _on_length_changed(self, idx):
        self.custom_length_box.setVisible(idx == 3)

    def get_options(self):
        # Length
        if self.length_combo.currentIndex() == 0:
            length = "short"
        elif self.length_combo.currentIndex() == 1:
            length = "medium"
        elif self.length_combo.currentIndex() == 2:
            length = "long"
        else:
            length = str(self.custom_length_box.value())
        # Style
        style = "paragraph" if self.style_combo.currentIndex() == 0 else "bullet_points"
        # Keywords
        keywords = [k.strip() for k in self.keywords_edit.text().split(",") if k.strip()]
        # Target
        target = "selection" if self.target_selection.isChecked() else "full"
        return {
            "length": length,
            "style": style,
            "keywords": keywords,
            "target": target
        } 