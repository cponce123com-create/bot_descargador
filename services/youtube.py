"""
Servicio de descarga de YouTube.
Usa oEmbed API para info (sin bloqueos) y yt-dlp con cookies para descarga.
"""

import os
import json
import logging
import requests
import yt_dlp
from config import DOWNLOAD_DIR, YT_DLP_OPTIONS, HTTP_TIMEOUT

logger = logging.getLogger(__name__)

COOKIES_FILE = "cookies.txt"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}


def _get_oembed_info(url):
    """
    Obtiene info basica via oEmbed API de YouTube.
    No requiere autenticacion y funciona desde cualquier IP.
    """
    try:
        oembed_url = "https://www.youtube.com/oembed"
        resp = requests.get(
            oembed_url,
            params={"url": url, "format": "json"},
            headers=_HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "title": data.get("title", "Video"),
            "author": data.get("author_name", "Desconocido"),
            "duration": 0,  # oEmbed no da duracion :(
            "thumbnail": data.get("thumbnail_url", ""),
        }
    except Exception as e:
        logger.warning("oEmbed fallo: %s", e)
        return None


def _estimate_duration(url):
    """
    Intenta obtener la duracion via scraping minimo.
    Si falla, retorna 0.
    """
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "extractor_args": {"youtube": "player_client=android"},
            "http_headers": _HEADERS,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return info.get("duration", 0)
    except Exception:
        pass
    return 0


def get_video_info(url):
    """
    Obtiene informacion del video.
    Usa oEmbed API (no requiere auth) + yt-dlp flat como respaldo.
    Retorna un dict con title, duration, formats (lista basica).
    """
    # 1. Intentar con oEmbed (funciona siempre)
    oembed = _get_oembed_info(url)
    if oembed:
        duration = _estimate_duration(url)
        # Formato unico (simplificado - sin lista real de formatos)
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
        return {
            "title": oembed["title"],
            "duration": duration or 0,
            "formats": formats,
        }

    # 2. Fallback: yt-dlp con extract_flat
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "http_headers": _HEADERS,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return {
                    "title": info.get("title", "Video"),
                    "duration": info.get("duration", 0),
                    "formats": [
                        {"format_id": "best", "ext": "mp4", "filesize": 0,
                         "format_note": "Mejor calidad", "resolution": "1080p",
                         "acodec": "aac", "vcodec": "h264"},
                        {"format_id": "best[height<=720]", "ext": "mp4",
                         "filesize": 0, "format_note": "HD 720p",
                         "resolution": "720p", "acodec": "aac", "vcodec": "h264"},
                    ],
                }
    except Exception as e:
        logger.error("get_video_info fallo: %s", e)

    return None


def _build_ydl_opts(extra_opts=None, for_download=True):
    """Construye opciones para yt-dlp, incluyendo cookies si existen."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extractor_retries": 3,
        "retries": 5,
        "fragment_retries": 5,
        "http_headers": _HEADERS,
    }

    if for_download:
        opts["extractor_args"] = {"youtube": "player_client=android"}

    # Usar cookies si existen
    if os.path.isfile(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
        logger.info("Usando cookies de %s", COOKIES_FILE)

    if extra_opts:
        opts.update(extra_opts)
    return opts


def download_video(url, format_id="best"):
    """Descarga un video de YouTube."""
    opts = _build_ydl_opts(
        extra_opts={
            **YT_DLP_OPTIONS,
            "format": format_id,
            "max_filesize": 48 * 1024 * 1024,
        }
    )
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
    except Exception as e:
        logger.error("Error descargando %s: %s", url, e)
        return None


def download_audio(url):
    """Descarga solo el audio (MP3)."""
    opts = _build_ydl_opts(
        extra_opts={
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
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = os.path.splitext(filename)[0] + ".mp3"
            return filename if os.path.isfile(filename) else None
    except Exception as e:
        logger.error("Error descargando audio %s: %s", url, e)
        return None
