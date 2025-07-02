import os
import sys
import logging
import requests
from PIL import Image
from io import BytesIO
import hashlib

logging.basicConfig(level=logging.INFO)

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


def thumb_cache_path(url):
    key = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"thumb_{key}.png")


def download_image(url, size=(120, 68)):
    cache_path = thumb_cache_path(url)
    if os.path.exists(cache_path):
        try:
            img = Image.open(cache_path).resize(size)
            return img
        except Exception:
            os.remove(cache_path)
    try:
        resp = safe_requests_get(url, timeout=10)
        resp.raise_for_status()
        if not resp.headers.get("Content-Type", "").startswith("image/"):
            raise ValueError("Invalid content type, expected image")
        img = Image.open(BytesIO(resp.content)).resize(size)
        img.save(cache_path)
        return img
    except Exception as e:
        logging.info(f"Image download failed for {url}: {e}")
        return None


def get_default_download_folder():
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            CSIDL_PERSONAL = 0x0005  # My Documents
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf)
            doc_path = buf.value
            downloads = os.path.join(os.path.dirname(doc_path), "Downloads")
            if os.path.exists(downloads):
                return downloads
        except Exception as e:
            logging.info(f"Could not detect Windows Downloads folder: {e}")
        return os.path.join(os.path.expanduser("~"), "Downloads")
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Downloads")
    else:
        return os.path.expanduser("~/Downloads")
