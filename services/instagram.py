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

def _run(args, timeout=240):
    cmd = [YT]
    if os.path.isfile(COOKIES_FILE): cmd.extend(["--cookies",COOKIES_FILE])
    cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode==0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired: return False,"","TIMEOUT"
    except Exception as e: return False,"",str(e)

def get_instagram_info(url):
    # Intentar obtener info básica
    ok, o, s = _run(["--get-title", url], 30)
    if ok:
        return {"title": o or "Instagram Media"}
    return {"title": "Instagram Media"}

def download_instagram(url):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"ig_{uniq}.%(ext)s")
    
    # Instagram a veces es caprichoso con los formatos, intentamos 'best'
    ok, sout, serr = _run(["--format", "best", "--output", o] + BASE + [url])
    
    if ok:
        for fn in os.listdir(DOWNLOAD_DIR):
            if uniq in fn and os.path.isfile(fp := os.path.join(DOWNLOAD_DIR, fn)) and os.path.getsize(fp) > 1024:
                return fp, ""
    
    return None, serr[:100] or "Error"
