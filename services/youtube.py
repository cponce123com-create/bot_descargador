"""
Servicio de descarga de YouTube usando yt-dlp.
Con multiples estrategias para evitar bloqueos.
"""

import os
import logging
import yt_dlp
from config import DOWNLOAD_DIR, YT_DLP_OPTIONS

logger = logging.getLogger(__name__)

# Headers realistas
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Distintas estrategias de extraccion para YouTube
_EXTRACTOR_ARGS = [
    # Estrategia 1: Android (menos bloqueado)
    {"youtube": "player_client=android"},
    # Estrategia 2: Web + Android
    {"youtube": "player_client=web,android"},
    # Estrategia 3: Sin restricciones
    {},
]


def _build_opts(extra_opts=None, extractor_args_idx=0):
    """Construye opciones de yt-dlp con la estrategia indicada."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extractor_retries": 3,
        "retries": 5,
        "fragment_retries": 5,
        "ignoreerrors": False,
        "http_headers": {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es,en;q=0.9",
        },
    }
    if _EXTRACTOR_ARGS[extractor_args_idx]:
        opts["extractor_args"] = _EXTRACTOR_ARGS[extractor_args_idx]
    if extra_opts:
        opts.update(extra_opts)
    return opts


def get_video_info(url):
    """Obtiene informacion de un video de YouTube.
    Prueba multiples estrategias si alguna falla."""
    
    last_error = None
    
    # Intentar con cada estrategia
    for idx in range(len(_EXTRACTOR_ARGS)):
        try:
            opts = _build_opts(extractor_args_idx=idx)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    continue
                formats = []
                for f in info.get("formats", []):
                    if f.get("vcodec") != "none" or f.get("acodec") != "none":
                        formats.append({
                            "format_id": f.get("format_id"),
                            "ext": f.get("ext"),
                            "filesize": f.get("filesize") or f.get("filesize_approx", 0),
                            "format_note": f.get("format_note", ""),
                            "acodec": f.get("acodec", "none"),
                            "vcodec": f.get("vcodec", "none"),
                            "resolution": f.get("resolution", ""),
                        })
                return {
                    "title": info.get("title", "Video"),
                    "duration": info.get("duration", 0),
                    "formats": formats,
                }
        except Exception as e:
            last_error = str(e)
            logger.warning("Estrategia %d fallo para %s: %s", idx, url, last_error)
            continue
    
    logger.error("Todas las estrategias fallaron para %s: %s", url, last_error)
    return None


def download_video(url, format_id="best"):
    """Descarga un video de YouTube."""
    opts = _build_opts(
        extra_opts={
            **YT_DLP_OPTIONS,
            "format": format_id,
            "max_filesize": 48 * 1024 * 1024,
        },
        extractor_args_idx=1,  # Usar web+android para descarga
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
    """Descarga solo el audio (MP3) de un video de YouTube."""
    opts = _build_opts(
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
        },
        extractor_args_idx=1,
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
