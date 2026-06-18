"""
Servicio de descarga de TikTok sin marca de agua usando TikWM API.
Retorna (filepath, direct_url, error) - intenta primero envio directo por URL.
"""

import os
import requests
import logging
from config import DOWNLOAD_DIR, HTTP_TIMEOUT, DOWNLOAD_TIMEOUT
from services.file_utils import sanitize_filename, cleanup

logger = logging.getLogger(__name__)


def download_tiktok_no_watermark(url):
    """
    Retorna (filepath: str|None, direct_url: str|None, error: str|None).
    El handler debe intentar direct_url primero, y si falla, usar filepath.
    """
    CHUNK_SIZE = 256 * 1024
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
            api_url, data={"url": url, "hd": "1"},
            headers=headers, timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            fp = _fallback_download(url)
            return fp, None, None if fp else "error"

        video_url = data.get("data", {}).get("play")
        if not video_url:
            fp = _fallback_download(url)
            return fp, None, None if fp else "error"

        # Descargar localmente como fallback
        title = data.get("data", {}).get("title", "tiktok_video")
        filename = sanitize_filename(f"{title}.mp4")
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        video_resp = requests.get(
            video_url,
            headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14)"},
            timeout=DOWNLOAD_TIMEOUT,
            stream=True,
        )
        video_resp.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in video_resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

        if os.path.isfile(filepath) and os.path.getsize(filepath) > 1024:
            # Devolver tambien la URL directa para que el handler intente envio directo
            return filepath, video_url, None

        cleanup(filepath)
        fp = _fallback_download(url)
        return fp, video_url, None if fp else "error"

    except Exception as e:
        logger.warning("TikTok download failed: %s", e)
        fp = _fallback_download(url)
        return fp, None, None if fp else "error"


def _fallback_download(url):
    try:
        import yt_dlp
        opts = {
            "quiet": True, "no_warnings": True,
            "outtmpl": f"{DOWNLOAD_DIR}/tiktok_fallback_%(id)s.%(ext)s",
            "max_filesize": 48 * 1024 * 1024,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if os.path.isfile(filename):
                return filename
    except Exception as e:
        logger.warning("TikTok fallback download failed: %s", e)
    return None
