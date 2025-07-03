# YouTube Video Downloader

A cross-platform desktop application to download YouTube videos with a simple PyQt5 GUI, powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

---

## Features

- Download YouTube videos with a clean graphical interface
- Automatic download of ffmpeg if not present
- Works on Windows and macOS
- Built with: PyQt5, yt-dlp, requests, Pillow
- Note: This application has only been tested on Windows. Mac users may need to make additional adjustments.

---

## Screenshots

Here are some screenshots of the application:

![ss-1](images/ss-1.png)
![ss-2](images/ss-2.png)
![ss-3](images/ss-3.png)
![ss-4](images/ss-4.png)
![ss-5](images/ss-5.png)
![ss-6](images/ss-6.png)
![ss-7](images/ss-7.png)
![ss-8](images/ss-8.png)

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
- This application has only been tested on Windows. Mac users may need to make additional adjustments.
- You can also run `python gui.py` for GUI testing.

---

## License

See `LICENSE.txt` for license details.

---

## Troubleshooting

- If you have issues, check your Python version (`python --version`), make sure dependencies are installed, and try running from a clean virtual environment.

---

## Contact

Created by [Shiva Aryal](https://github.com/ShivaArya1)
