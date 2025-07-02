# YouTube Video Downloader

A cross-platform desktop application to download YouTube videos with a simple PyQt5 GUI, powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

---

## Features

- Download YouTube videos with a clean graphical interface
- Automatic download of ffmpeg if not present
- Works on Windows and macOS
- Built with: PyQt5, yt-dlp, requests, Pillow

---

## Getting Started

### 1. Requirements

- **Python 3.7 or later**  
  [Download Python here](https://www.python.org/downloads/)

### 2. Download & Extract

- Download the code (via GitHub "Code" > "Download ZIP")
- Unzip to a folder, e.g., `youtube_video_downloader/`

### 3. Open Terminal/Command Prompt

- **Windows:** Shift+Right Click in the folder > “Open PowerShell window here”
- **macOS/Linux:** Open Terminal and `cd` to the folder

### 4. (Optional) Create a Virtual Environment

```bash
python -m venv venv
# Activate on Windows:
venv\Scripts\activate
# Activate on macOS/Linux:
source venv/bin/activate
```

### 5. Install Dependencies

You can use either method below:

**a) Using setup.py (recommended):**

```bash
pip install .
```

**b) Or, install manually:**

```bash
pip install PyQt5 yt-dlp requests Pillow
```

### 6. Run the Application

```bash
python main.py
```

- The GUI window should open.
- Paste YouTube links and download!

---

## Notes

- **ffmpeg** will be downloaded automatically on first run (no setup needed).
- If you get a missing module error, make sure your virtual environment is active and dependencies installed.
- You can also run `python gui.py` for GUI testing.

---

## License

See `LICENSE.txt` for license details.

---

## Troubleshooting

- If you have issues, check your Python version (`python --version`), make sure dependencies are installed, and try running from a clean virtual environment.

---

## Contact

Created by Shiva Aryal.
