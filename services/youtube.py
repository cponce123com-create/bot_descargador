"""YouTube downloader con yt-dlp + requests."""

import os, subprocess, logging, requests
from config import DOWNLOAD_DIR, COOKIES_FILE, HTTP_TIMEOUT
logger = logging.getLogger(__name__)
YT_DLP = "yt-dlp"
MAX_SIZE = 300 * 1024 * 1024
UA = "Mozilla/5.0 Chrome/125.0.0.0"

# Flags comunes para extraer un solo video (no playlist)
SINGLE = ["--no-playlist", "--playlist-end", "1"]

def _get_oembed_info(url):
    try:
        resp = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
        resp.raise_for_status(); d = resp.json()
        return {"title": d.get("title", "Video"), "author": d.get("author_name", "")}
    except: return None

def get_video_info(url):
    o = _get_oembed_info(url)
    if o: return {"title": o["title"], "duration": 0, "formats": [
        {"format_id": "best", "ext": "mp4", "format_note": "Mejor calidad", "resolution": "1080p"},
        {"format_id": "best[height<=720]", "ext": "mp4", "format_note": "HD 720p", "resolution": "720p"},
        {"format_id": "worst", "ext": "mp4", "format_note": "Baja calidad", "resolution": "360p"}]}
    return None

def _run_ytdlp(args, timeout=60):
    cmd = [YT_DLP, "--no-warnings"]
    if os.path.isfile(COOKIES_FILE): cmd.extend(["--cookies", COOKIES_FILE])
    cmd.extend(args)
    logger.info("CMD: %s", " ".join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        s, o = r.stderr.strip(), r.stdout.strip()
        if r.returncode != 0:
            logger.warning("FALLO (rc=%d): %s", r.returncode, s[:500])
            return False, o, s
        return True, o, s
    except subprocess.TimeoutExpired:
        logger.error("TIMEOUT %ss", timeout)
        return False, "", "TIMEOUT"
    except Exception as e:
        logger.error("EXC: %s", e)
        return False, "", str(e)

def _is_env_err(s):
    m = ["no video formats found", "no supported javascript runtime", "could not install"]
    return any(x in s.lower() for x in m)

def validate_cookies():
    if not os.path.isfile(COOKIES_FILE): return False, "No hay cookies.txt"
    ok, o, s = _run_ytdlp(["--simulate", "--print", "title", "--format", "best"] + SINGLE + ["https://www.youtube.com/watch?v=jNQXAC9IVRw"], timeout=30)
    if _is_env_err(s): logger.error("ENV ERROR"); return False, "ENV_ERROR"
    if "Sign in to confirm" in s: return False, "YOUTUBE_BLOCK"
    if ok and o.strip(): logger.info("Cookies validadas OK"); return True, "OK"
    return False, s[:200] if s else "Error"

def _get_direct_url(url, fmt, timeout=60):
    ok, out, err = _run_ytdlp(["--quiet", "--simulate", "--print", "url", "--format", fmt] + SINGLE + [url], timeout=timeout)
    if _is_env_err(err): return False, "", "ENV_ERROR"
    if ok and out:
        for line in out.split(chr(10)):
            if line.startswith("http"): return True, line, ""
    if not ok and "Sign in" in err: return False, "", "YOUTUBE_BLOCK"
    if not ok and "Private video" in err: return False, "", "VIDEO_PRIVADO"
    if not ok and "Video unavailable" in err: return False, "", "VIDEO_NO_DISPONIBLE"
    if not ok and "Requested format" in err: return False, "", "FORMATO_NO_DISPONIBLE"
    if not ok and "TIMEOUT" in err: return False, "", "TIMEOUT"
    return False, "", (err[:300] if err else "Error")

def _download_url(vurl, path):
    try:
        resp = requests.get(vurl, stream=True, timeout=120, headers={"User-Agent": UA})
        resp.raise_for_status()
        with open(path, "wb") as f:
            for c in resp.iter_content(8192):
                if c: f.write(c)
                if os.path.getsize(path) > MAX_SIZE: os.remove(path); return False, "ARCHIVO_MUY_GRANDE"
        return (os.path.isfile(path) and os.path.getsize(path) > 1024), ""
    except Exception as e:
        if os.path.isfile(path): os.remove(path)
        return False, str(e)[:150]

def download_video(url, format_id="best"):
    specs = {"best": ["best","bestvideo+bestaudio","best[ext=mp4]","18"],
             "best[height<=720]": ["best[height<=720]","bestvideo[height<=720]+bestaudio","best","18"],
             "worst": ["worst","18","best"]}
    last = ""
    for fmt in specs.get(format_id, ["best","18"]):
        logger.info("Formato: %s", fmt)
        ok, vurl, err = _get_direct_url(url, fmt)
        if not ok:
            last = err
            if any(x in err for x in ["YOUTUBE_BLOCK","PRIVADO","NO_DISPONIBLE","ENV_ERROR","TIMEOUT"]): return None, err
            continue
        p = os.path.join(DOWNLOAD_DIR, "yt_video.mp4")
        ok, err = _download_url(vurl, p)
        if ok: logger.info("OK: %s (%d MB)", p, os.path.getsize(p)//1024//1024); return p, ""
        last = err
    return None, last or "FORMATO_NO_DISPONIBLE"

def download_audio(url):
    ok, vurl, err = _get_direct_url(url, "bestaudio/best")
    if not ok: return None, err
    p = os.path.join(DOWNLOAD_DIR, "yt_audio.mp3")
    ok, err = _download_url(vurl, p)
    return (p,"") if ok else (None, err)