"""
Servicio de descarga de YouTube.
Usa oEmbed API para info y yt-dlp con/ sin cookies para descarga.
"""

import os
import logging
import requests
import yt_dlp
from config import DOWNLOAD_DIR, YT_DLP_OPTIONS, HTTP_TIMEOUT

logger = logging.getLogger(__name__)

COOKIES_FILE = os.path.abspath("cookies.txt")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}


def _get_oembed_info(url):
    try:
        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            headers=_HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "title": data.get("title", "Video"),
            "author": data.get("author_name", "Desconocido"),
            "thumbnail": data.get("thumbnail_url", ""),
        }
    except Exception as e:
        logger.warning("oEmbed fallo: %s", e)
        return None


def _estimate_duration(url):
    try:
        opts = {
            "quiet": True, "no_warnings": True,
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
    """Obtiene info del video via oEmbed API (sin bloqueos)."""
    oembed = _get_oembed_info(url)
    if oembed:
        duration = _estimate_duration(url)
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
        return {"title": oembed["title"], "duration": duration or 0, "formats": formats}
    return None


def _try_download(url, opts):
    """Intenta descargar con opciones dadas. Retorna path o None."""
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
            if os.path.isfile(filename):
                size = os.path.getsize(filename)
                logger.info("Descargado %s: %s (%d MB)", url, filename, size // 1024 // 1024)
                return filename
    except Exception as e:
        logger.warning("Intento fallo: %s", e)
    return None


def _build_opts(extra_opts, use_cookies=True):
    """Construye opciones para yt-dlp."""
    opts = {
        "quiet": True, "no_warnings": True,
        "extractor_retries": 3, "retries": 5, "fragment_retries": 5,
        "http_headers": _HEADERS,
        "extractor_args": {"youtube": "player_client=android"},
        "max_filesize": 50 * 1024 * 1024,  # 50MB
    }
    if use_cookies and os.path.isfile(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
        logger.info("Usando cookies para descarga")
    opts.update(extra_opts)
    return opts


def download_video(url, format_id="best"):
    """Descarga un video probando estrategias."""
    base_opts = {
        "quiet": True, "no_warnings": True,
        "extractor_retries": 3, "retries": 5, "fragment_retries": 5,
        "http_headers": _HEADERS,
        "max_filesize": 300 * 1024 * 1024,
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "restrictfilenames": True,
    }

    # Multiples formatos a probar (del mas especifico al mas generico)
    formatos_a_probar = [format_id]
    if format_id == "best[height<=720]":
        formatos_a_probar = [
            "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "best[height<=720]",
            "best",
        ]
    elif format_id == "worst":
        formatos_a_probar = ["worst", "best"]

    strategies = []
    for fmt in formatos_a_probar:
        strategies.append({**base_opts, "format": fmt, "extractor_args": {"youtube": "player_client=android"}})
        strategies.append({**base_opts, "format": fmt})

    # Agregar cookies a TODAS las estrategias
    if os.path.isfile(COOKIES_FILE):
        # Debug: ver formato de cookies
        try:
            with open(COOKIES_FILE) as cf:
                first = cf.readline().strip()
            logger.info("Cookies formato: %s", first[:100])
        except Exception:
            pass
        for strat in strategies:
            strat["cookiefile"] = COOKIES_FILE
        logger.info("Cookies agregadas a %d estrategias", len(strategies))

    for i, opts in enumerate(strategies):
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
                if os.path.isfile(filename):
                    fsize = os.path.getsize(filename)
                    logger.info("Estrategia %d OK: %s (%d MB)", i, filename, fsize // 1024 // 1024)
                    return filename
        except Exception as e:
            logger.warning("Estrategia %d: %s", i, str(e)[:150])
            continue

    logger.error("Todas las estrategias fallaron para %s", url)
    return None


def download_audio(url):
    """Descarga solo audio MP3."""
    opts = {
        "quiet": True, "no_warnings": True,
        "extractor_retries": 3, "retries": 5, "fragment_retries": 5,
        "http_headers": _HEADERS,
        "extractor_args": {"youtube": "player_client=android"},
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "restrictfilenames": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "max_filesize": 300 * 1024 * 1024,
    }
    if os.path.isfile(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
        logger.info("Usando cookies para descarga de audio")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = os.path.splitext(filename)[0] + ".mp3"
            if os.path.isfile(filename):
                return filename
            # Buscar cualquier .mp3 en downloads
            for f in os.listdir(DOWNLOAD_DIR):
                if f.endswith(".mp3") and not f.startswith("._"):
                    return os.path.join(DOWNLOAD_DIR, f)
    except Exception as e:
        logger.error("Error descargando audio: %s", str(e)[:200])
    return None
