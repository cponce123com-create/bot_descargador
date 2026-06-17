"""
Servicio de descarga de YouTube usando yt-dlp.
"""

import os
from typing import Optional
import yt_dlp
from config import DOWNLOAD_DIR, YT_DLP_OPTIONS


def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title", "Video"),
                "duration": info.get("duration", 0),
                "formats": [
                    {
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "filesize": f.get("filesize") or f.get("filesize_approx", 0),
                        "format_note": f.get("format_note", ""),
                        "acodec": f.get("acodec", "none"),
                        "vcodec": f.get("vcodec", "none"),
                        "resolution": f.get("resolution", ""),
                    }
                    for f in info.get("formats", [])
                    if f.get("vcodec") != "none" or f.get("acodec") != "none"
                ],
            }
    except Exception:
        return None


def download_video(url, format_id="best"):
    opts = {
        **YT_DLP_OPTIONS,
        "format": format_id,
        "max_filesize": 48 * 1024 * 1024,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.isfile(filename):
                base, _ = os.path.splitext(filename)
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(os.path.basename(base)):
                        filename = os.path.join(DOWNLOAD_DIR, f)
                        break
            return filename if os.path.isfile(filename) else None
    except Exception:
        return None


def download_audio(url):
    opts = {
        **YT_DLP_OPTIONS,
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = os.path.splitext(filename)[0] + ".mp3"
            return filename if os.path.isfile(filename) else None
    except Exception:
        return None
