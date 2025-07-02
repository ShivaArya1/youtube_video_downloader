import os
import requests
import zipfile
import shutil
import yt_dlp
from PyQt5.QtCore import QObject, pyqtSignal
import json
import hashlib
import logging

logging.basicConfig(level=logging.INFO)

FFMPEG_FILENAME = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def safe_requests_get(*args, **kwargs):
    try:
        response = requests.get(*args, **kwargs)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        logging.info(f"[ERROR] Request failed: {e}")
        return None


def info_cache_path(url):
    key = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"info_{key}.json")


def ensure_ffmpeg(progress_callback=None):
    if os.path.exists(FFMPEG_FILENAME):
        return True
    if os.name != "nt":
        return True
    try:
        if progress_callback:
            progress_callback("Downloading ffmpeg...")
        r = safe_requests_get(FFMPEG_URL, stream=True)
        zippath = os.path.join(CACHE_DIR, "ffmpeg_tmp.zip")
        with open(zippath, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
        with zipfile.ZipFile(zippath) as z:
            exe_member = None
            for member in z.namelist():
                if member.endswith("bin/ffmpeg.exe"):
                    exe_member = member
                    break
            if not exe_member:
                raise Exception("ffmpeg.exe not found in zip.")
            z.extract(exe_member, path=CACHE_DIR)
            ffmpeg_src = os.path.join(CACHE_DIR, exe_member)
            ffmpeg_dst = FFMPEG_FILENAME
            if os.path.exists(ffmpeg_dst):
                os.remove(ffmpeg_dst)
            shutil.move(ffmpeg_src, ffmpeg_dst)
            # Clean up empty folders created during extraction
            extracted_root = os.path.join(
                CACHE_DIR, exe_member.split("bin/")[0].strip("/")
            )
            if os.path.exists(extracted_root):
                shutil.rmtree(extracted_root, ignore_errors=True)
        os.remove(zippath)
        return True
    except Exception as e:
        logging.exception("Could not download ffmpeg")
        return False


def get_video_info(url):
    cache_path = info_cache_path(url)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            os.remove(cache_path)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": False}) as ydl:
            info = ydl.extract_info(url, download=False)
            if "entries" in info:
                entries = [entry for entry in info["entries"] if entry]
                out = [entry for entry in entries if "webpage_url" in entry]
            else:
                out = [info]
            # --- Ensure cache directory exists before writing ---
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(out, f)
            return out
    except Exception as e:
        logging.exception("Error extracting video info")
        return None


def get_resolutions(info):
    resolutions = set()
    for f in info.get("formats", []):
        if f.get("vcodec") != "none" and f.get("ext") == "mp4" and f.get("height"):
            resolutions.add(f"{f['height']}p")
    return sorted(resolutions, key=lambda x: int(x.replace("p", "")), reverse=True)


def get_format_for_resolution(info, resolution):
    best_fmt = None
    best_height = 0
    for f in info.get("formats", []):
        if f.get("vcodec") != "none" and f.get("ext") == "mp4" and f.get("height"):
            height = f["height"]
            if f"{height}p" == resolution:
                if best_fmt is None or f.get("filesize", 0) > best_fmt.get(
                    "filesize", 0
                ):
                    best_fmt = f
            elif int(resolution.replace("p", "")) < height and (
                best_height == 0 or height < best_height
            ):
                best_fmt = f
                best_height = height
    return best_fmt.get("format_id") if best_fmt else None


class DownloadWorker(QObject):
    progress = pyqtSignal(int, float, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, url, out_folder, format_id=None, output_filename=None):
        super().__init__()
        self.abort = False
        self.url = url
        self.out_folder = out_folder
        self.format_id = format_id
        self.output_filename = output_filename

    def run(self):
        if not ensure_ffmpeg():
            self.finished.emit(
                False, "Failed to download ffmpeg for merging video/audio!"
            )
            return

        def hook_fn(d):
            if d["status"] == "downloading":
                if self.abort:
                    raise Exception("Download aborted")
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes", 0)
                percent = int((done / total * 100) if total and total != 0 else 0)
                speed = d.get("speed") or 0.0
                eta = d.get("eta") or 0
                self.progress.emit(percent, float(speed), int(eta))
            elif d["status"] == "finished":
                self.progress.emit(100, 0.0, 0)

        fmt = (
            f"{self.format_id}+bestaudio/best"
            if self.format_id
            else "bestvideo+bestaudio/best"
        )
        if self.output_filename:
            outtmpl = os.path.join(self.out_folder, self.output_filename)
        else:
            outtmpl = os.path.join(self.out_folder, "%(title)s.%(ext)s")
        ydl_opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "quiet": True,
            "noplaylist": True,
            "progress_hooks": [hook_fn],
            "merge_output_format": "mp4",
            "ffmpeg_location": os.path.abspath(FFMPEG_FILENAME),
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished.emit(True, "")
        except Exception as e:
            if str(e) == "Download aborted":
                # User cancelled, do not log as error
                self.finished.emit(False, "Download cancelled by user")
            else:
                logging.exception("Download failed")
                self.finished.emit(False, str(e))
