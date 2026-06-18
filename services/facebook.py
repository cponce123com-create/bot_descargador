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

def _run(args, timeout=240):
    cmd = [YT, "--no-check-certificates", "--no-cache-dir"]
    if os.path.isfile(COOKIES_FILE): cmd.extend(["--cookies",COOKIES_FILE])
    cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode==0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired: return False,"","TIMEOUT"
    except Exception as e: return False,"",str(e)

def get_video_info(url):
    # Intentar obtener info básica usando yt-dlp
    ok, o, s = _run(["--get-title", "--get-duration", url], 30)
    if ok:
        lines = o.split('\n')
        title = lines[0] if lines else "Facebook Video"
        return {"title": title}
    return {"title": "Facebook Video"}

def download_facebook(url):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    # Intentar descargar la mejor calidad disponible que sea mp4 o combinable a mp4
    o = os.path.join(DOWNLOAD_DIR, f"fb_{uniq}.%(ext)s")
    
    # Facebook a veces requiere formatos específicos o falla con 'best'
    # Intentamos una estrategia similar a YouTube pero simplificada
    formats = ["bestvideo+bestaudio/best", "best"]
    
    last_err = ""
    for fmt in formats:
        ok, sout, serr = _run(["--format", fmt, "--output", o] + BASE + SINGLE + [url])
        if ok:
            for fn in os.listdir(DOWNLOAD_DIR):
                if uniq in fn and os.path.isfile(fp := os.path.join(DOWNLOAD_DIR, fn)) and os.path.getsize(fp) > 1024:
                    return fp, ""
        last_err = serr[:100] or "Error"
    
    return None, last_err
