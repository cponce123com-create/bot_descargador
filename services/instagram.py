"""Instagram downloader - async-safe via subprocess."""

import os, subprocess, logging, uuid
from config import DOWNLOAD_DIR, COOKIES_FILE
logger = logging.getLogger(__name__); YT = "yt-dlp"

BASE = [
    "--no-warnings",
    "--quiet",
    "--no-mtime",
    "--force-overwrites",
    "--max-filesize", "300M",
    "--merge-output-format", "mp4",
    "--concurrent-fragments", "5",
    "--buffer-size", "16K",
    "--no-check-certificates",
    "--no-cache-dir"
]

def _cleanup():
    if not os.path.isdir(DOWNLOAD_DIR): return
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".part") or f.endswith(".ytdl"):
            try: os.remove(os.path.join(DOWNLOAD_DIR,f))
            except: pass

def _run(args, timeout=240, progress_callback=None):
    from services.youtube import _run as yt_run
    return yt_run(args, timeout, progress_callback)

def get_instagram_info(url):
    # Intentar obtener info básica
    ok, o, s = _run(["--get-title", url], 30)
    if ok:
        return {"title": o or "Instagram Media"}
    return {"title": "Instagram Media"}

def download_instagram(url, progress_callback=None):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"ig_{uniq}.%(ext)s")
    ok, sout, serr = _run(["--format", "best", "--output", o] + BASE + [url], progress_callback=progress_callback)
    if ok:
        for fn in os.listdir(DOWNLOAD_DIR):
            if uniq in fn and os.path.isfile(fp := os.path.join(DOWNLOAD_DIR, fn)) and os.path.getsize(fp) > 1024:
                return fp, ""
    return None, serr[:100] or "Error"

def download_instagram_audio(url, progress_callback=None):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"ig_audio_{uniq}.%(ext)s")
    ok, sout, serr = _run(["--format", "bestaudio/best", "--extract-audio", "--audio-format", "mp3", "--output", o] + BASE + [url], progress_callback=progress_callback)
    if ok:
        for fn in os.listdir(DOWNLOAD_DIR):
            if uniq in fn and fn.endswith(".mp3") and os.path.getsize(fp := os.path.join(DOWNLOAD_DIR, fn)) > 1024:
                return fp, ""
    return None, serr[:100] or "Error"
