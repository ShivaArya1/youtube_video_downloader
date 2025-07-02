from setuptools import setup

setup(
    name="youtube_video_downloader",
    version="1.0.0",
    description="A PyQt5 GUI YouTube video downloader using yt_dlp.",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Shiva Aryal",
    author_email="aryal.shiva55@outlook.com",
    url="https://github.com/ShivaArya1/youtube_video_downloader",
    license="Custom License",
    py_modules=[
        "downloader",
        "ffmpeg_loader",
        "gui",
        "main",
        "main_with_splash",
        "utils",
    ],
    install_requires=[
        "PyQt5>=5.15.0",
        "yt_dlp>=2023.3.4",
        "requests>=2.20.0",
        "Pillow>=8.0.0",
    ],
    python_requires=">=3.7",
    entry_points={
        "gui_scripts": [
            "youtube_downloader=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: Other/Proprietary License",
        "Intended Audience :: End Users/Desktop",
        "Environment :: Win32 (MS Windows)",
        "Environment :: MacOS X",
        "Topic :: Multimedia :: Video",
        "Topic :: Utilities",
    ],
)
