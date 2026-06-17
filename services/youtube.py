"""
Servicio de descarga de YouTube.
"""

import os, subprocess, logging, requests
from config import DOWNLOAD_DIR, COOKIES_FILE, HTTP_TIMEOUT
logger = logging.getLogger(__name__)
YT_DLP = "yt-dlp"
MAX_SIZE = 300 * 1024 * 1024
UA = "Mozilla/5.0 Chrome/125.0.0.0"

def _get_oembed_info(url):
    try:
        resp = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        d = resp.json()
        return {"title": d.get("title", "Video"), "author": d.get("author_name", "")}
    except: return None

def get_video_info(url):
    o = _get_oembed_info(url)
    if o: return {"title": o["title"], "duration": 0, "formats": [
        {"format_id": "best", "ext": "mp4", "format_note": "Mejor calidad", "resolution": "1080p"},
        {"format_id": "best[height<=720]", "ext": "mp4", "format_note": "HD 720p", "resolution": "720p"},
        {"format_id": "worst", "ext": "mp4", "format_note": "Baja calidad", "resolution": "360p"}]}
    return None

def _run_ytdlp(args):
    cmd = [YT_DLP, "--no-warnings"]
    if os.path.isfile(COOKIES_FILE): cmd.extend(["--cookies", COOKIES_FILE])
    cmd.extend(args)
    logger.info("CMD: %s", " ".join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        s, o = r.stderr.strip(), r.stdout.strip()
        if r.returncode != 0:
            logger.warning("FALLO yt-dlp (rc=%d): %s", r.returncode, s[:500])
            return False, o, s
        logger.info("OK yt-dlp: %s", o[:200])
        return True, o, s
    except Exception as e:
        logger.error("EXC yt-dlp: %s", e)
        return False, "", str(e)

# Detecta errores de entorno (sin runtime JS) vs cookies invalidas
def _is_env_error(stderr):
    """Retorna True si el error es de entorno/runtime, no de cookies."""
    env_markers = [
        "No video formats found",
        "No supported JavaScript runtime",
        "Could not install JavaScript runtime",
        "deno", "bun", "node",  # si menciona runtimes es probablemente error de entorno
    ]
    return any(m in stderr.lower() for m in [x.lower() for x in env_markers])

def validate_cookies():
    if not os.path.isfile(COOKIES_FILE): return False, "No hay cookies.txt"
    cmd = [YT_DLP, "--cookies", COOKIES_FILE, "--no-warnings", "--quiet", "--simulate", "--print", "title", "--format", "best", "--playlist-end", "1", "https://www.youtube.com/watch?v=jNQXAC9IVRw"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    stderr = r.stderr.strip()
    if _is_env_error(stderr):
        logger.error("ERROR DE ENTORNO: yt-dlp no tiene runtime JS. Falta Deno o yt-dlp-ejs.")
        return False, "ENV_ERROR: Falta runtime JavaScript (Deno). Error del servidor."
    if "Sign in to confirm" in stderr:
        return False, "YOUTUBE_BLOCK"
    if r.returncode == 0 and r.stdout.strip():
        logger.info("Cookies validadas OK")
        return True, "Cookies OK"
    return False, stderr[:200] if stderr else "Error"

def _get_direct_url(url, fmt):
    ok, out, err = _run_ytdlp(["--quiet", "--simulate", "--print", "url", "--format", fmt, url])
    if _is_env_error(err):
        logger.error("ERROR DE ENTORNO en _get_direct_url: %s", err[:300])
        return False, "", "ENV_ERROR: Error del servidor. Reintenta mas tarde."
    if ok and out:
        for line in out.split(chr(10)):
            if line.startswith("http"): return True, line, ""
    if "Sign in" in err: return False, "", "YOUTUBE_BLOCK"
    if "Private video" in err: return False, "", "VIDEO_PRIVADO"
    if "Video unavailable" in err: return False, "", "VIDEO_NO_DISPONIBLE"
    if "Requested format" in err: return False, "", "FORMATO_NO_DISPONIBLE"
    return False, "", err[:300] if err else "Error"

def _download_url(video_url, path):
    try:
        resp = requests.get(video_url, stream=True, timeout=120, headers={"User-Agent": UA})
        resp.raise_for_status()
        total = 0
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                if chunk: total += len(chunk); f.write(chunk)
                if total > MAX_SIZE: os.remove(path); return False, "ARCHIVO_MUY_GRANDE"
        return (os.path.isfile(path) and os.path.getsize(path) > 1024), ""
    except Exception as e:
        if os.path.isfile(path): os.remove(path)
        return False, str(e)[:150]

def download_video(url, format_id="best"):
    specs = {"best": ["best", "bestvideo+bestaudio", "best[ext=mp4]", "18"],
             "best[height<=720]": ["best[height<=720]", "bestvideo[height<=720]+bestaudio", "best", "18"],
             "worst": ["worst", "18", "best"]}
    last = ""
    for fmt in specs.get(format_id, ["best", "18"]):
        logger.info("Formato: %s", fmt)
        ok, url_url, err = _get_direct_url(url, fmt)
        if not ok:
            last = err
            if any(x in err for x in ["YOUTUBE_BLOCK", "PRIVADO", "NO_DISPONIBLE", "ENV_ERROR"]): return None, err
            continue
        path = os.path.join(DOWNLOAD_DIR, "yt_video.mp4")
        ok, err = _download_url(url_url, path)
        if ok:
            s = os.path.getsize(path) // 1024 // 1024
            logger.info("OK: %s (%d MB)", path, s)
            return path, ""
        last = err
    return None, last or "FORMATO_NO_DISPONIBLE"

def download_audio(url):
    ok, vurl, err = _get_direct_url(url, "bestaudio/best")
    if not ok: return None, err
    path = os.path.join(DOWNLOAD_DIR, "yt_audio.mp3")
    ok, err = _download_url(vurl, path)
    return (path, "") if ok else (None, err)