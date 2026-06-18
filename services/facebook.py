"""Facebook downloader - async-safe via subprocess."""

import os, subprocess, logging, uuid
from config import DOWNLOAD_DIR, COOKIES_FILE
logger = logging.getLogger(__name__); YT = "yt-dlp"

SINGLE = ["--no-playlist","--playlist-end","1"]
BASE = [
    "--no-warnings",
    "--quiet",
    "--no-mtime",
    "--force-overwrites",
    "--max-filesize", "300M",
    "--merge-output-format", "mp4",
    "--concurrent-fragments", "5",
    "--buffer-size", "16K"
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

def get_video_info(url):
    # Intentar obtener info básica usando yt-dlp
    ok, o, s = _run(["--get-title", "--get-duration", url], 30)
    if ok:
        lines = o.split('\n')
        title = lines[0] if lines else "Facebook Video"
        return {"title": title}
    return {"title": "Facebook Video"}

def download_facebook(url, progress_callback=None):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"fb_{uniq}.%(ext)s")
    formats = ["bestvideo+bestaudio/best", "best"]
    
    last_err = ""
    for fmt in formats:
        ok, sout, serr = _run(["--format", fmt, "--output", o] + BASE + SINGLE + [url], progress_callback=progress_callback)
        if ok:
            for fn in os.listdir(DOWNLOAD_DIR):
                if uniq in fn and os.path.isfile(fp := os.path.join(DOWNLOAD_DIR, fn)) and os.path.getsize(fp) > 1024:
                    return fp, ""
        last_err = serr[:100] or "Error"
    
    return None, last_err

def download_facebook_audio(url, progress_callback=None):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"fb_audio_{uniq}.%(ext)s")
    ok, sout, serr = _run(["--format", "bestaudio/best", "--extract-audio", "--audio-format", "mp3", "--output", o] + BASE + SINGLE + [url], progress_callback=progress_callback)
    if ok:
        for fn in os.listdir(DOWNLOAD_DIR):
            if uniq in fn and fn.endswith(".mp3") and os.path.getsize(fp := os.path.join(DOWNLOAD_DIR, fn)) > 1024:
                return fp, ""
    return None, serr[:100] or "Error"
