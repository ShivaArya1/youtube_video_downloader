# --- Standard and PyQt5 imports ---
import os
import re
import json
import hashlib
import urllib.parse
import string
import logging
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QTableWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QComboBox,
    QProgressBar,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QDialog,
    QLineEdit,
    QSizePolicy,
    QMenu,
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from functools import partial

import downloader
from utils import download_image, get_default_download_folder

# --- Logging configuration ---
logging.basicConfig(level=logging.INFO)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
SETTINGS_FILE = os.path.join(CACHE_DIR, "settings.json")


def choose_folder_dialog(parent, current_folder):
    if os.path.exists(current_folder):
        folder = QFileDialog.getExistingDirectory(
            parent, "Select Download Folder", current_folder
        )
    else:
        folder = QFileDialog.getExistingDirectory(parent, "Select Download Folder")
    return folder


def strip_playlist_param(url):
    parts = urllib.parse.urlsplit(url)
    qs = urllib.parse.parse_qs(parts.query)
    if "list" in qs:
        del qs["list"]
    new_query = urllib.parse.urlencode(qs, doseq=True)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


def sanitize_filename(name):
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    return "".join(c if c in valid_chars else "_" for c in name)


def uniquify_filename(folder, base, ext):
    filename = f"{base}{ext}"
    i = 1
    while os.path.exists(os.path.join(folder, filename)):
        filename = f"{base}_{i}{ext}"
        i += 1
    return filename


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 220)
        self.layout = QVBoxLayout(self)
        self.res_combo = QComboBox()
        self.res_combo.addItems(
            ["Highest available", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
        )
        self.layout.addWidget(QLabel("Default Download Resolution:"))
        self.layout.addWidget(self.res_combo)
        self.layout.addWidget(QLabel("Default Download Folder:"))
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.browse_btn = QPushButton("Browse")
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.browse_btn)
        self.layout.addLayout(folder_layout)
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.layout.addWidget(self.clear_cache_btn)
        self.clear_settings_btn = QPushButton("Clear Settings")
        self.layout.addWidget(self.clear_settings_btn)
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        self.layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn.clicked.connect(self.reject)
        self.browse_btn.clicked.connect(self.browse_folder)
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        self.clear_settings_btn.clicked.connect(self.clear_settings)
        self.load_settings()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                s = json.load(f)
            self.res_combo.setCurrentText(
                s.get("default_resolution", "Highest available")
            )
            self.folder_edit.setText(
                s.get("default_download_folder", get_default_download_folder())
            )
        else:
            self.folder_edit.setText(get_default_download_folder())

    def save_settings(self):
        s = {
            "default_resolution": self.res_combo.currentText(),
            "default_download_folder": self.folder_edit.text(),
        }
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f)
        self.accept()

    def browse_folder(self):
        folder = choose_folder_dialog(self, self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def clear_cache(self):
        cache_path = CACHE_DIR
        removed = 0
        if os.path.exists(cache_path):
            for fn in os.listdir(cache_path):
                if fn == "settings.json":
                    continue
                fp = os.path.join(cache_path, fn)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                        removed += 1
                except Exception as e:
                    logging.exception("Error clearing cache file:")
        QMessageBox.information(
            self, "Cache Cleared", f"Removed {removed} cache files."
        )

    def clear_settings(self):
        ret = QMessageBox.warning(
            self,
            "Clear Settings",
            "Are you sure you want to clear all settings?\n"
            "Default settings will be applied next time you open the app.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            try:
                if os.path.exists(SETTINGS_FILE):
                    os.remove(SETTINGS_FILE)
                QMessageBox.information(
                    self,
                    "Settings Cleared",
                    "Settings have been cleared. Default settings will be used next time.",
                )
                self.load_settings()
            except Exception as e:
                logging.exception("Error clearing settings file:")
                QMessageBox.warning(self, "Error", "Could not clear settings file.")


class RowData:
    def __init__(self, url, info, default_resolution):
        self.url = url
        self.title = info.get("title", "")
        self.thumb_url = info.get("thumbnail", "")
        self.resolutions = downloader.get_resolutions(info)
        if default_resolution and default_resolution in self.resolutions:
            self.selected_resolution = default_resolution
        else:
            self.selected_resolution = self.resolutions[0] if self.resolutions else None
        self.status = "Pending"
        self.progress = 0
        self.thumb_img = None
        self.info = info
        self.thread = None
        self.worker = None
        self.output_filename = None


class InfoWorker(QObject):
    result = pyqtSignal(object)
    done = pyqtSignal()

    def __init__(self, links, default_resolution):
        super().__init__()
        self.links = links
        self.default_resolution = default_resolution
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        for url in self.links:
            if self._abort:
                break
            try:
                results = downloader.get_video_info(url)
                if results is not None:
                    for info in results:
                        if self._abort:
                            break
                        row = RowData(
                            info.get("webpage_url", url), info, self.default_resolution
                        )
                        self.result.emit(row)
                else:
                    self.result.emit(None)
            except Exception as e:
                logging.exception("Error fetching video info:")
                self.result.emit(None)
        self.done.emit()


class DownloaderGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.resize(1200, 720)
        os.makedirs(CACHE_DIR, exist_ok=True)

        self.settings = self.load_settings()
        self.download_folder = self.settings.get(
            "default_download_folder", get_default_download_folder()
        )
        self.default_resolution = self.settings.get(
            "default_resolution", "Highest available"
        )
        self.queue = []
        self.max_active_downloads = 3
        self.active_downloads = 0
        self._sort_col = -1
        self._sort_asc = True
        self._sort_original = []

        self.init_ui()
        self.folder_label.setText(f"Download folder: {self.download_folder}")

        # --- Custom header context menu for reset sort ---
        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.header_context_menu)

        self.suppress_cancel_popup = False

    def header_context_menu(self, pos):
        header = self.table.horizontalHeader()
        menu = QMenu(self)
        reset_action = menu.addAction("Reset Sort")
        action = menu.exec_(header.mapToGlobal(pos))
        if action == reset_action:
            self.queue = list(self._sort_original)
            self._sort_col = -1
            self.refresh_table()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_settings(self):
        s = {
            "default_resolution": self.default_resolution,
            "default_download_folder": self.download_folder,
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f)

    def select_folder(self):
        folder = choose_folder_dialog(self, self.download_folder)
        if folder:
            self.download_folder = folder
            self.folder_label.setText(f"Download folder: {self.download_folder}")
            self.save_settings()

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec_():
            self.default_resolution = dlg.res_combo.currentText()
            self.download_folder = dlg.folder_edit.text()
            self.save_settings()
            self.folder_label.setText(f"Download folder: {self.download_folder}")
            QMessageBox.information(
                self, "Settings Saved", "Settings have been updated."
            )

    def init_ui(self):
        layout = QVBoxLayout(self)
        topbar = QHBoxLayout()
        title_label = QLabel("<b>YouTube Video Downloader</b>")
        title_label.setStyleSheet("font-size:18px; margin-left:8px;")
        topbar.addWidget(title_label)
        topbar.addStretch()
        settings_btn = QPushButton("Settings", self)
        settings_btn.setFixedWidth(120)
        settings_btn.clicked.connect(self.open_settings)
        topbar.addWidget(settings_btn)
        layout.addLayout(topbar)
        info_label = QLabel(
            "<b>Note:</b> For best results, copy the link from your browser's address bar."
            " Links copied from YouTube's right-click menu may include playlists and take longer to fetch.<br>"
            "<span style='color:#b55500;'>If fetching seems stuck, use the Stop button below.</span>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size:13px; color:#888; margin-bottom:6px;")
        layout.addWidget(info_label)
        url_layout = QHBoxLayout()
        self.url_input = QTextEdit(self)
        self.url_input.setPlaceholderText(
            "Paste video/playlist links here (one per line)"
        )
        self.url_input.setMaximumHeight(70)
        url_layout.addWidget(self.url_input)
        self.get_info_btn = QPushButton("Get Video Info", self)
        self.get_info_btn.setMinimumWidth(140)
        url_layout.addWidget(self.get_info_btn)
        self.stop_fetch_btn = QPushButton("Stop Fetch", self)
        self.stop_fetch_btn.setMinimumWidth(110)
        self.stop_fetch_btn.setEnabled(False)
        self.stop_fetch_btn.clicked.connect(self.stop_fetch)
        url_layout.addWidget(self.stop_fetch_btn)
        layout.addLayout(url_layout)

        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        # Set initial header labels (will be updated in refresh_table)
        self.table.setHorizontalHeaderLabels(
            ["Thumb", "Title ↑↓", "Resolution", "Status ↑↓", "Actions"]
        )
        self.table.setStyleSheet(
            """
            QTableWidget { font-size: 14px; }
            QHeaderView::section { background:#fafafa; padding:6px; font-weight:500;}
            QTableWidget::item { padding: 10px; }
            """
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(self.table.SelectItems)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(self.table.NoSelection)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 330)
        self.table.setColumnWidth(2, 240)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 170)
        self.table.verticalHeader().setDefaultSectionSize(80)

        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self.handle_sort)

        layout.addWidget(self.table, stretch=1)

        bottom_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download All", self)
        self.download_btn.setMinimumWidth(150)
        bottom_layout.addWidget(self.download_btn)
        self.cancel_all_btn = QPushButton("Cancel All", self)
        self.cancel_all_btn.setMinimumWidth(150)
        self.cancel_all_btn.clicked.connect(self.on_cancel_all)
        bottom_layout.addWidget(self.cancel_all_btn)
        self.folder_label = QLabel("", self)
        self.clear_btn = QPushButton("Clear Completed", self)
        self.clear_btn.setMinimumWidth(150)
        self.clear_btn.clicked.connect(self.clear_completed)
        bottom_layout.insertWidget(3, self.clear_btn)
        self.folder_btn = QPushButton("Select Folder", self)
        self.folder_btn.setMinimumWidth(150)
        bottom_layout.addWidget(self.folder_btn)
        bottom_layout.addWidget(self.folder_label)
        bottom_layout.addStretch()
        self.fetch_bar = QProgressBar(self)
        self.fetch_bar.setFixedWidth(180)
        self.fetch_bar.setRange(0, 0)
        self.fetch_bar.setTextVisible(True)
        self.fetch_bar.setFormat("Fetching info...")
        self.fetch_bar.hide()
        bottom_layout.addWidget(self.fetch_bar)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        self.download_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.cancel_all_btn.setEnabled(False)  # Initially disabled
        self.get_info_btn.clicked.connect(self.on_get_info)
        self.download_btn.clicked.connect(self.on_start_downloads)
        self.folder_btn.clicked.connect(self.select_folder)
        self.folder_label.setText(f"Download folder: {self.download_folder}")

    def refresh_table(self):
        self.table.setColumnCount(5)
        self.table.setRowCount(len(self.queue))
        downloadable = any(row.status in ("Pending", "Cancelled") for row in self.queue)
        self.download_btn.setEnabled(downloadable)
        clearable = any(row.status == "Completed" for row in self.queue)
        self.clear_btn.setEnabled(clearable)
        cancellable = any(row.status in ("Downloading", "Queued") for row in self.queue)
        self.cancel_all_btn.setEnabled(cancellable)
        if not self.queue:
            self.table.setRowCount(1)
            for col in range(5):
                self.table.setItem(0, col, QTableWidgetItem(""))
            item = QTableWidgetItem("No videos added.")
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 1, item)
            return
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 330)
        self.table.setColumnWidth(2, 240)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 170)
        self.table.verticalHeader().setDefaultSectionSize(80)

        for i, rowdata in enumerate(self.queue):
            thumb_lbl = QLabel()
            thumb_lbl.setAlignment(Qt.AlignCenter)
            if rowdata.thumb_img:
                thumb_lbl.setPixmap(rowdata.thumb_img)
            self.table.setCellWidget(i, 0, thumb_lbl)
            title_item = QTableWidgetItem(rowdata.title)
            title_item.setFlags(title_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 1, title_item)
            cb = QComboBox()
            cb.addItems(rowdata.resolutions)
            if rowdata.selected_resolution:
                cb.setCurrentText(rowdata.selected_resolution)
            cb.currentTextChanged.connect(partial(self.set_row_resolution, rowdata))
            cb.setEnabled(rowdata.status in ("Pending", "Cancelled"))
            self.table.setCellWidget(i, 2, cb)
            if rowdata.status == "Downloading":
                self.table.setItem(i, 3, None)
                self.table.setCellWidget(i, 3, None)
                pb = QProgressBar()
                pb.setValue(rowdata.progress)
                pb.setTextVisible(True)
                pb.setFixedHeight(20)
                pb.setFixedWidth(90)
                pb.setFormat(f"{rowdata.progress}%")
                pb_hbox = QHBoxLayout()
                pb_hbox.addStretch()
                pb_hbox.addWidget(pb)
                pb_hbox.addStretch()
                pb_hbox.setContentsMargins(0, 0, 0, 0)
                pb_vbox = QVBoxLayout()
                pb_vbox.addStretch()
                pb_vbox.addLayout(pb_hbox)
                pb_vbox.addStretch()
                pb_vbox.setContentsMargins(0, 0, 0, 0)
                pb_widget = QWidget()
                pb_widget.setLayout(pb_vbox)
                self.table.setCellWidget(i, 3, pb_widget)
            else:
                self.table.setCellWidget(i, 3, None)
                status_item = QTableWidgetItem(rowdata.status)
                status_item.setTextAlignment(Qt.AlignCenter)
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 3, status_item)
            action_widget = QWidget()
            hbox = QHBoxLayout()
            hbox.setContentsMargins(2, 2, 2, 2)
            hbox.setSpacing(6)
            dl_btn = QPushButton("⬇️")
            dl_btn.setToolTip("Download")
            dl_btn.setFixedWidth(36)
            dl_btn.setStyleSheet("font-size:20px;")
            dl_btn.setEnabled(rowdata.status in ("Pending", "Cancelled"))
            dl_btn.clicked.connect(partial(self.start_download, i))
            hbox.addWidget(dl_btn)
            rm_btn = QPushButton("🗑️")
            rm_btn.setToolTip("Remove from list")
            rm_btn.setFixedWidth(36)
            rm_btn.setStyleSheet("font-size:20px;")
            rm_btn.setEnabled(rowdata.status in ("Pending", "Cancelled"))
            rm_btn.clicked.connect(partial(self.confirm_remove_row, i))
            hbox.addWidget(rm_btn)
            if rowdata.status in ("Downloading", "Queued"):
                cancel_btn = QPushButton("✖️")
                cancel_btn.setToolTip("Cancel Download")
                cancel_btn.setFixedWidth(36)
                cancel_btn.setStyleSheet("font-size:20px;")
                cancel_btn.clicked.connect(partial(self.on_cancel, i))
                hbox.addWidget(cancel_btn)
            if rowdata.status == "Completed":
                open_btn = QPushButton("📂")
                open_btn.setToolTip("Open File")
                open_btn.setFixedWidth(36)
                open_btn.setStyleSheet("font-size:20px;")
                open_btn.clicked.connect(partial(self.on_open, i))
                hbox.addWidget(open_btn)
            action_widget.setLayout(hbox)
            self.table.setCellWidget(i, 4, action_widget)

    def on_get_info(self):
        if hasattr(self, "worker_thread") and self.worker_thread.isRunning():
            QMessageBox.information(self, "Busy", "Already fetching info. Please wait.")
            return
        text = self.url_input.toPlainText().strip()
        links = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(
                r"^https?://(?:www\.)?youtube\.com/playlist\?list=", line, re.I
            ):
                links.append(line)
            elif re.match(r"^https?://(?:www\.)?(youtube\.com|youtu\.be)/", line):
                links.append(strip_playlist_param(line))
            else:
                links.append(f"ytsearch:{line}")
        links = list(dict.fromkeys(links))
        if not links:
            QMessageBox.warning(self, "No Links", "No usable input or URLs found!")
            return
        self.get_info_btn.setEnabled(False)
        self.stop_fetch_btn.setEnabled(True)
        self.download_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.fetch_bar.show()
        self.worker_thread = QThread()
        self.info_worker = InfoWorker(links, self.default_resolution)
        self.info_worker.moveToThread(self.worker_thread)
        self.info_worker.result.connect(self.add_info_row)
        self.info_worker.done.connect(self.info_fetch_done)
        self.worker_thread.started.connect(self.info_worker.run)
        self.worker_thread.start()

    def info_fetch_done(self):
        self.get_info_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.fetch_bar.hide()
        self.url_input.clear()
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.refresh_table()
        self.stop_fetch_btn.setEnabled(False)
        if hasattr(self, "_info_errors"):
            QMessageBox.warning(
                self,
                "Invalid Link",
                f"Some links were invalid or not supported ({self._info_errors}).",
            )
            del self._info_errors

    def stop_fetch(self):
        ret = QMessageBox.question(
            self,
            "Stop Fetching?",
            "Are you sure you want to stop fetching video information?\n"
            "Fetching may take time, especially for playlists.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            if hasattr(self, "info_worker"):
                try:
                    self.info_worker.abort()
                except Exception as e:
                    logging.exception("Error aborting info worker:")
            if hasattr(self, "worker_thread"):
                try:
                    self.worker_thread.quit()
                    self.worker_thread.wait()
                except Exception as e:
                    logging.exception("Error quitting worker thread:")
            self.get_info_btn.setEnabled(True)
            self.download_btn.setEnabled(True)
            self.url_input.setEnabled(True)
            self.fetch_bar.hide()
            self.stop_fetch_btn.setEnabled(False)

    def add_info_row(self, rowdata):
        if rowdata is None:
            if not hasattr(self, "_info_errors"):
                self._info_errors = 1
            else:
                self._info_errors += 1
            return
        if not any(r.url == rowdata.url for r in self.queue):
            self.load_thumb(rowdata)
            self.queue.append(rowdata)
            self._sort_original.append(rowdata)
            self.refresh_table()

    def load_thumb(self, rowdata):
        img = download_image(rowdata.thumb_url)
        if img:
            img = img.convert("RGBA").resize((120, 68))
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            rowdata.thumb_img = QPixmap.fromImage(qimg)

    def set_row_resolution(self, rowdata, value):
        rowdata.selected_resolution = value

    def on_start_downloads(self):
        for idx, rowdata in enumerate(self.queue):
            if rowdata.status in ("Pending", "Queued", "Cancelled"):
                rowdata.status = "Queued"
        self.process_download_queue()
        self.refresh_table()

    def process_download_queue(self):
        for idx, rowdata in enumerate(self.queue):
            if (
                rowdata.status == "Queued"
                and self.active_downloads < self.max_active_downloads
            ):
                self.active_downloads += 1
                self.start_download(idx)
        self.refresh_table()

    def start_download(self, idx):
        rowdata = self.queue[idx]
        res = rowdata.selected_resolution or (
            rowdata.resolutions[0] if rowdata.resolutions else None
        )
        fmt_id = downloader.get_format_for_resolution(rowdata.info, res)
        base = sanitize_filename(rowdata.title)
        ext = ".mp4"
        unique_filename = uniquify_filename(self.download_folder, base, ext)
        rowdata.output_filename = unique_filename
        rowdata.status = "Downloading"
        rowdata.progress = 0
        rowdata.download_folder = self.download_folder
        self.refresh_table()
        rowdata.thread = QThread()
        rowdata.worker = downloader.DownloadWorker(
            rowdata.url, self.download_folder, fmt_id, output_filename=unique_filename
        )
        rowdata.worker.moveToThread(rowdata.thread)
        rowdata.thread.started.connect(rowdata.worker.run)
        rowdata.worker.progress.connect(
            lambda percent, speed, eta, url=rowdata.url: self.update_progress(
                url, percent
            )
        )
        rowdata.worker.finished.connect(
            lambda success, msg, url=rowdata.url, thread=rowdata.thread: self.finish_download_by_url(
                url, success, msg, thread
            )
        )
        rowdata.thread.start()

    def update_progress(self, url, percent):
        for idx, rowdata in enumerate(self.queue):
            if rowdata.url == url:
                rowdata.progress = percent
                if rowdata.status == "Downloading":
                    cell_widget = self.table.cellWidget(idx, 3)
                    if cell_widget:
                        for child in cell_widget.findChildren(QProgressBar):
                            child.setValue(percent)
                            child.setFormat(f"{percent}%")
                break

    def finish_download_by_url(self, url, success, msg, thread):
        for rowdata in self.queue:
            if rowdata.url == url:
                self.active_downloads = max(0, self.active_downloads - 1)
                if success:
                    rowdata.status = "Completed"
                    rowdata.progress = 100
                else:
                    rowdata.status = "Cancelled"
                thread.quit()
                thread.wait()
                rowdata.worker = None
                rowdata.thread = None
                break
        self.process_download_queue()
        self.refresh_table()

    def on_cancel(self, idx):
        # Only show confirmation if not suppressing popups (i.e., not from Cancel All)
        if not self.suppress_cancel_popup:
            ret = QMessageBox.question(
                self,
                "Cancel Download",
                "Are you sure you want to cancel this download?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return

        rowdata = self.queue[idx]
        was_downloading = rowdata.status == "Downloading"
        if getattr(rowdata, "worker", None):
            try:
                rowdata.worker.abort = True
            except Exception:
                pass
        if getattr(rowdata, "thread", None):
            try:
                rowdata.thread.quit()
                rowdata.thread.wait()
            except Exception:
                pass
            rowdata.worker = None
            rowdata.thread = None
        rowdata.status = "Cancelled"
        rowdata.progress = 0
        if was_downloading:
            self.active_downloads = max(0, self.active_downloads - 1)
        self.refresh_table()
        self.process_download_queue()

    def on_cancel_all(self):
        ret = QMessageBox.question(
            self,
            "Cancel All Downloads",
            "Are you sure you want to cancel all active downloads?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return

        self.suppress_cancel_popup = True
        cancelled_any = False
        for idx, rowdata in enumerate(self.queue):
            if rowdata.status in ("Downloading", "Queued"):
                self.on_cancel(idx)
                cancelled_any = True
        self.suppress_cancel_popup = False
        self.refresh_table()
        if cancelled_any:
            QMessageBox.information(
                self, "Downloads Cancelled", "All active downloads have been cancelled."
            )

    def remove_row(self, idx):
        if 0 <= idx < len(self.queue):
            rowdata = self.queue[idx]
            was_downloading = rowdata.status == "Downloading"
            if rowdata.status in ("Downloading", "Queued"):
                if rowdata.worker:
                    rowdata.worker.abort = True
                if rowdata.thread:
                    rowdata.thread.quit()
                    rowdata.thread.wait()
                    rowdata.worker = None
                    rowdata.thread = None
        del self.queue[idx]
        if rowdata in self._sort_original:
            self._sort_original.remove(rowdata)
        if was_downloading:
            self.active_downloads = max(0, self.active_downloads - 1)
        self.refresh_table()
        self.process_download_queue()

    def confirm_remove_row(self, idx):
        ret = QMessageBox.question(
            self,
            "Remove Video",
            "Are you sure you want to remove this video from the list?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.remove_row(idx)

    def on_open(self, idx):
        rowdata = self.queue[idx]
        if rowdata.status != "Completed":
            return
        try:
            base = sanitize_filename(rowdata.title)
            for ext in [".mp4", ".mkv", ".webm"]:
                file_path = os.path.join(self.download_folder, f"{base}{ext}")
                if os.path.exists(file_path):
                    os.startfile(file_path)
                    return
            QMessageBox.information(
                self, "File Not Found", "Cannot find the downloaded file."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {e}")

    def clear_completed(self):
        completed = [row for row in self.queue if row.status == "Completed"]
        self.queue = [row for row in self.queue if row.status != "Completed"]
        for row in completed:
            if row in self._sort_original:
                self._sort_original.remove(row)
        self.refresh_table()

    def handle_sort(self, col):
        # Only allow sorting on Title (1) and Status (3)
        if col not in [1, 3]:
            return
        header = self.table.horizontalHeader()
        labels = [
            "Thumb",
            "Title",
            "Resolution",
            "Status",
            "Actions",
        ]

        # Cycle: None -> Asc -> Desc -> None
        if self._sort_col == col:
            if self._sort_asc:
                self._sort_asc = False
                arrow = "↓"
            else:
                self._sort_col = -1
                header.setSortIndicatorShown(False)
                self.queue = list(self._sort_original)
                # Show both arrows on sortable columns when reset
                labels[1] = "Title ↑↓"
                labels[3] = "Status ↑↓"
                self.table.setHorizontalHeaderLabels(labels)
                self.refresh_table()
                return
        else:
            self._sort_col = col
            self._sort_asc = True
            arrow = "↑"

        # Sort the queue
        if col == 1:
            self.queue.sort(key=lambda r: r.title, reverse=not self._sort_asc)
        elif col == 3:
            self.queue.sort(key=lambda r: r.status, reverse=not self._sort_asc)

        header.setSortIndicatorShown(False)  # hide Qt arrow
        # Show arrow only on the sorted column, both arrows on the other sortable column
        if col == 1:
            labels[1] = f"Title {arrow}"
            labels[3] = "Status ↑↓"
        elif col == 3:
            labels[1] = "Title ↑↓"
            labels[3] = f"Status {arrow}"
        self.table.setHorizontalHeaderLabels(labels)
        self.refresh_table()

    def closeEvent(self, event):
        # Clear cache directory except settings.json
        failed_files = []
        try:
            if os.path.exists(CACHE_DIR):
                for fn in os.listdir(CACHE_DIR):
                    if fn == "settings.json":
                        continue
                    fp = os.path.join(CACHE_DIR, fn)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except Exception as e:
                            logging.exception("Error clearing cache on exit:")
                            failed_files.append(fn)
        except Exception as e:
            logging.exception("Error clearing cache on exit:")

        event.accept()
