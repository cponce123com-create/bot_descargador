"""
Servicio de descarga de YouTube.
Usa yt-dlp --simulate --print url para obtener URL directa,
luego descarga con requests (no necesita ffmpeg).
"""

import os
import subprocess
import logging
import requests
from config import DOWNLOAD_DIR, HTTP_TIMEOUT

logger = logging.getLogger(__name__)

COOKIES_FILE = "cookies.txt"
YT_DLP = "yt-dlp"
MAX_SIZE = 300 * 1024 * 1024


def _get_oembed_info(url):
    try:
        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            headers={"User-Agent": "Mozilla/5.0 Chrome/125.0.0.0"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"title": data.get("title", "Video"), "author": data.get("author_name", "")}
    except Exception as e:
        logger.warning("oEmbed fallo: %s", e)
        return None


def get_video_info(url):
    oembed = _get_oembed_info(url)
    if oembed:
        formats = [
            {"format_id": "best", "ext": "mp4", "filesize": 0,
             "format_note": "Mejor calidad", "resolution": "1080p",
             "acodec": "aac", "vcodec": "h264"},
            {"format_id": "best[height<=720]", "ext": "mp4", "filesize": 0,
             "format_note": "HD 720p", "resolution": "720p",
             "acodec": "aac", "vcodec": "h264"},
            {"format_id": "worst", "ext": "mp4", "filesize": 0,
             "format_note": "Baja calidad", "resolution": "360p",
             "acodec": "aac", "vcodec": "h264"},
        ]
        return {"title": oembed["title"], "duration": 0, "formats": formats}
    return None


def _get_direct_url(url, format_spec):
    """Obtiene URL directa de descarga via yt-dlp --simulate --print url."""
    cmd = [YT_DLP, "--no-warnings", "--quiet", "--simulate", "--print", "url",
           "--format", format_spec, url]
    if os.path.isfile(COOKIES_FILE):
        cmd.insert(1, "--cookies")
        cmd.insert(2, COOKIES_FILE)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 or result.stdout.strip():
            lines = result.stdout.strip().split(chr(10))
            return lines[0] if lines else None
        logger.warning("get_url fallo: %s", result.stderr[:200])
    except Exception as e:
        logger.warning("get_url exception: %s", e)
    return None


def _download_from_url(video_url, output_path, expected_size=0):
    """Descarga un video desde una URL directa."""
    try:
        resp = requests.get(video_url, stream=True, timeout=120,
                           headers={"User-Agent": "Mozilla/5.0 Chrome/125.0.0.0"})
        resp.raise_for_status()

        total = 0
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    total += len(chunk)
                    if total > MAX_SIZE:
                        os.remove(output_path)
                        logger.warning("Archivo >300MB, cancelado")
                        return None
                    f.write(chunk)

        if os.path.isfile(output_path) and os.path.getsize(output_path) > 1024:
            return output_path
    except Exception as e:
        logger.warning("download_url fallo: %s", e)
        if os.path.isfile(output_path):
            os.remove(output_path)
    return None


def download_video(url, format_id="best"):
    """Descarga un video. Obtiene URL directa con yt-dlp, descarga con requests."""
    # Mapa de format_id a format_spec de yt-dlp
    format_specs = {
        "best": ["best", "bestvideo[height<=1080]+bestaudio", "best[ext=mp4]", "18"],
        "best[height<=720]": ["best[height<=720]", "bestvideo[height<=720]+bestaudio",
                             "bestvideo[height<=480]+bestaudio", "best", "18"],
        "worst": ["worst", "18"],
    }

    specs = format_specs.get(format_id, ["best", "18"])

    for spec in specs:
        logger.info("Intentando formato: %s", spec)
        video_url = _get_direct_url(url, spec)
        if not video_url:
            continue

        if not video_url.startswith("http"):
            continue

        # Determinar extension
        ext = "mp4"
        if "mime=audio" in video_url or "audio" in spec.lower():
            ext = "mp3"

        outpath = os.path.join(DOWNLOAD_DIR, f"yt_video.{ext}")
        result = _download_from_url(video_url, outpath)
        if result:
            size = os.path.getsize(result)
            logger.info("Descargado: %s (%d MB)", result, size // 1024 // 1024)
            return result

    logger.error("Todos los intentos fallaron para %s", url)
    return None


def download_audio(url):
    """Descarga solo audio usando yt-dlp."""
    # Obtener URL del audio
    cmd = [YT_DLP, "--no-warnings", "--quiet", "--simulate", "--print", "url",
           "--format", "bestaudio/best", url]
    if os.path.isfile(COOKIES_FILE):
        cmd.insert(1, "--cookies")
        cmd.insert(2, COOKIES_FILE)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not result.stdout.strip():
            return None

            lines = result.stdout.strip().split(chr(10))
            return lines[0] if lines else None
        outpath = os.path.join(DOWNLOAD_DIR, "yt_audio.mp3")

        resp = requests.get(audio_url, stream=True, timeout=120,
                           headers={"User-Agent": "Mozilla/5.0 Chrome/125.0.0.0"})
        resp.raise_for_status()

        total = 0
        with open(outpath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    total += len(chunk)
                    if total > MAX_SIZE:
                        os.remove(outpath)
                        return None
                    f.write(chunk)

        if os.path.isfile(outpath) and os.path.getsize(outpath) > 1024:
            return outpath
    except Exception as e:
        logger.warning("download_audio fallo: %s", e)
    return None
