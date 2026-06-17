"""
Servicio de descarga de YouTube.
Usa subprocess para ejecutar yt-dlp (evita bugs del binding Python).
"""

import os
import subprocess
import logging
import requests
from config import DOWNLOAD_DIR, HTTP_TIMEOUT

logger = logging.getLogger(__name__)

COOKIES_FILE = "cookies.txt"
YT_DLP = "yt-dlp"  # asume que esta en PATH


def _get_oembed_info(url):
    try:
        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"title": data.get("title", "Video"), "author": data.get("author_name", "")}
    except Exception as e:
        logger.warning("oEmbed fallo: %s", e)
        return None


def get_video_info(url):
    """Obtiene info via oEmbed API (sin bloqueos)."""
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


def _run_ytdlp(args):
    """Ejecuta yt-dlp como subprocess. Retorna True si tuvo exito."""
    cmd = [YT_DLP, "--no-warnings", "--quiet"]
    if os.path.isfile(COOKIES_FILE):
        cmd.extend(["--cookies", COOKIES_FILE])
        logger.info("Usando cookies via --cookies flag")
    cmd.extend(args)
    logger.info("Ejecutando: %s", " ".join(cmd[-8:]))

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        stderr = result.stderr.strip()[:300]
        logger.warning("yt-dlp fallo: %s", stderr)
        return False, stderr
    return True, result.stdout


def download_video(url, format_id="best"):
    """Descarga un video probando diferentes formatos."""
    outtmpl = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    # Probamos formatos de mas especifico a mas generico
    # sin extractor-args (a veces con extractor-args cambian los IDs)
    formatos_probar = ["best", "bestvideo+bestaudio", "18"]

    if format_id == "best[height<=720]":
        formatos_probar = [
            "best[height<=720]",
            "bestvideo[height<=720]+bestaudio",
            "bestvideo+bestaudio",
            "best",
            "18",
        ]
    elif format_id == "worst":
        formatos_probar = ["worst", "18", "best"]

    for fmt in formatos_probar:
        args = [
            "--format", fmt,
            "--max-filesize", "300M",
            "--output", outtmpl,
            "--restrict-filenames",
            "--merge-output-format", "mp4",
            "--retries", "5",
            "--fragment-retries", "5",
            url,
        ]
        ok, err = _run_ytdlp(args)
        if ok:
            for f in os.listdir(DOWNLOAD_DIR):
                if not f.startswith("._"):
                    fpath = os.path.join(DOWNLOAD_DIR, f)
                    if os.path.isfile(fpath) and os.path.getsize(fpath) > 1024:
                        logger.info("Descargado: %s (%d MB)", fpath, os.path.getsize(fpath) // 1024 // 1024)
                        return fpath
        else:
            # Solo continuar si es error de formato
            if "Requested format" in err or "not available" in err:
                logger.info("Formato %s no disponible, probando siguiente", fmt)
                continue
            else:
                logger.warning("Error diferente para formato %s: %s", fmt, err)
                continue  # No romper, probar siguiente

    logger.error("Todos los intentos fallaron para %s", url)
    return None


def download_audio(url):
    """Descarga solo audio MP3."""
    outtmpl = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    args = [
        "--format", "bestaudio/best",
        "--max-filesize", "300M",
        "--output", outtmpl,
        "--restrict-filenames",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--retries", "5",
        "--fragment-retries", "5",
        url,
    ]
    ok, _ = _run_ytdlp(args)
    if ok:
        for f in os.listdir(DOWNLOAD_DIR):
            if f.endswith(".mp3") and not f.startswith("._"):
                return os.path.join(DOWNLOAD_DIR, f)
    return None
