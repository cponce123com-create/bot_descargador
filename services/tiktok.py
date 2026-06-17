"""
Servicio de descarga de TikTok sin marca de agua usando TikWM API.
Fallback a yt-dlp.
"""

import os
import requests
from typing import Optional
from config import DOWNLOAD_DIR, HTTP_TIMEOUT, DOWNLOAD_TIMEOUT
from services.file_utils import sanitize_filename, cleanup


def download_tiktok_no_watermark(url):
    filepath = None
    try:
        api_url = "https://www.tikwm.com/api/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 14; SM-S928B) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(
            api_url,
            data={"url": url, "hd": "1"},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return _fallback_download(url)

        video_url = data.get("data", {}).get("play")
        if not video_url:
            return _fallback_download(url)

        title = data.get("data", {}).get("title", "tiktok_video")
        filename = sanitize_filename(f"{title}.mp4")
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        video_resp = requests.get(
            video_url,
            headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14)"},
            timeout=DOWNLOAD_TIMEOUT,
        )
        video_resp.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(video_resp.content)

        if os.path.isfile(filepath) and os.path.getsize(filepath) > 1024:
            return filepath
        cleanup(filepath)
        return _fallback_download(url)

    except Exception:
        cleanup(filepath)
        return _fallback_download(url)


def _fallback_download(url):
    try:
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": f"{DOWNLOAD_DIR}/tiktok_fallback_%(id)s.%(ext)s",
            "max_filesize": 48 * 1024 * 1024,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if os.path.isfile(filename):
                return filename
    except Exception:
        pass
    return None
