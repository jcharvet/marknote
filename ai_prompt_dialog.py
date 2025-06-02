from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox

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