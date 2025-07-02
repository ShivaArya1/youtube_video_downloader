import sys
import logging
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt, QTimer
from gui import DownloaderGUI
import downloader


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setFixedSize(400, 120)
        self.setStyleSheet("background-color: #333; color: white; font-size: 14px;")

        self.layout = QVBoxLayout()
        self.label = QLabel("Checking for FFmpeg...")
        self.label.setAlignment(Qt.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.progress)
        self.setLayout(self.layout)

    def update_text(self, text):
        self.label.setText(text)


def main():
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()

    def start_main_app():
        splash.update_text("Downloading FFmpeg...")

        def progress_callback(msg):
            splash.update_text(msg)
            QApplication.processEvents()

        if not downloader.ensure_ffmpeg(progress_callback):
            splash.update_text("FFmpeg download failed!")
            QTimer.singleShot(2000, app.quit)
            return

        splash.close()
        win = DownloaderGUI()
        win.show()

    QTimer.singleShot(300, start_main_app)  # Start shortly after splash

    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("Unhandled exception:")
