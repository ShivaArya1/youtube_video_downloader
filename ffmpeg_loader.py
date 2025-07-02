import subprocess


def is_ffmpeg_available():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QProgressBar,
    QPushButton,
    QApplication,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
import downloader


class FFmpegWorker(QThread):
    progress_msg = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._abort = False

    def run(self):
        def progress_callback(msg):
            if self._abort:
                return
            self.progress_msg.emit(msg)

        success = downloader.ensure_ffmpeg(progress_callback)
        if not self._abort:
            self.finished.emit(success)

    def abort(self):
        self._abort = True


class FFmpegLoaderWidget(QWidget):
    def __init__(self, callback_on_finish):
        super().__init__()
        self.callback_on_finish = callback_on_finish
        self.user_cancel = False
        self.setWindowTitle("FFmpeg Setup")
        self.setFixedSize(440, 150)
        self.setWindowFlags(
            Qt.Window
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
        )
        self.setStyleSheet("font-size: 12px;")

        self.layout = QVBoxLayout()
        self.status_label = QLabel("Preparing FFmpeg for use. Please wait...")
        self.sub_label = QLabel("Initializing...")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.handle_cancel)

        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.sub_label)
        self.layout.addWidget(self.progress)
        self.layout.addWidget(self.cancel_btn, alignment=Qt.AlignRight)
        self.setLayout(self.layout)

        self.worker = FFmpegWorker()
        self.worker.progress_msg.connect(self.update_text)
        self.worker.finished.connect(self.finish)
        self.worker.start()

    def update_text(self, msg):
        self.sub_label.setText(msg)

    def finish(self, success):
        self.progress.setRange(0, 1)
        self.sub_label.setText(
            "FFmpeg is ready. Launching..." if success else "FFmpeg setup failed."
        )
        QTimer.singleShot(1000, self.launch_main)

    def launch_main(self):
        self.user_cancel = False
        self.close()
        self.callback_on_finish()

    def handle_cancel(self):
        self.user_cancel = True
        self.close()

    def closeEvent(self, event):
        if self.user_cancel:
            self.worker.abort()
            reply = QMessageBox.warning(
                self,
                "Cancel FFmpeg Setup?",
                "If you cancel FFmpeg setup, you may not be able to download high-quality videos. Are you sure you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                event.accept()
                self.callback_on_finish()
            else:
                self.user_cancel = False  # Reset flag, stay open
                event.ignore()
        else:
            event.accept()
