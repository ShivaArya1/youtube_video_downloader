import sys
import os
import shutil
import logging
from PyQt5.QtWidgets import QApplication
from gui import DownloaderGUI
from ffmpeg_loader import FFmpegLoaderWidget


def launch_main_gui():
    global main_window
    main_window = DownloaderGUI()
    main_window.show()


def main():
    app = QApplication(sys.argv)
    ffmpeg_path = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    ffmpeg_exists = os.path.exists(ffmpeg_path) or shutil.which(ffmpeg_path)
    if not ffmpeg_exists:
        splash = FFmpegLoaderWidget(callback_on_finish=launch_main_gui)
        splash.show()
    else:
        launch_main_gui()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("Unhandled exception:")
