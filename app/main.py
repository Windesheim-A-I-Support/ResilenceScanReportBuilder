import os
import subprocess
import sys

import requests
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# --- Build Metadata ---

APP_VERSION = os.environ.get("APP_VERSION", "dev").lstrip("v")
BUILD_NUMBER = os.environ.get("BUILD_NUMBER", "0")
COMMIT_SHA = os.environ.get("COMMIT_SHA", "unknown")[:7]

REPO_NAME = os.environ.get("REPO_NAME", "MyApp")
APP_NAME = REPO_NAME.replace("-", " ").title()


def check_for_updates(current_version):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        return

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    r = requests.get(url)
    if r.status_code == 200:
        latest = r.json()["tag_name"].lstrip("v")
        if latest != current_version:
            print("Update available:", latest)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            f"{APP_NAME} v{APP_VERSION} build {BUILD_NUMBER} ({COMMIT_SHA})"
        )

        layout = QVBoxLayout()

        self.label = QLabel("Press the button to run Python task")
        layout.addWidget(self.label)

        self.button = QPushButton("Run Task")
        self.button.clicked.connect(self.run_task)
        layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

    def run_task(self):
        result = subprocess.run(
            ["python", "--version"],
            capture_output=True,
            text=True,
        )
        self.label.setText(result.stdout.strip())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
