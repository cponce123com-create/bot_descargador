"""YouTube downloader - async-safe via subprocess."""

import os, subprocess, logging, uuid
from config import DOWNLOAD_DIR, COOKIES_FILE
logger = logging.getLogger(__name__)
YT = "yt-dlp"

SINGLE = ["--no-playlist", "--playlist-end", "1"]

# Opciones comunes para todas las descargas
BASE_OPTS = [
    "--no-warnings", "--quiet",
    "--no-mtime", "--force-overwrites",
    "--concurrent-fragments", "4",
    "--max-filesize", "300M",
    "--merge-output-format", "mp4",
]

def _cleanup_stale():
    """Limpia archivos huerfanos/part de descargas fallidas."""
    if not os.path.isdir(DOWNLOAD_DIR): return
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith("._"): continue
        fp = os.path.join(DOWNLOAD_DIR, f)
        try:
            if os.path.isfile(fp) and (f.endswith(".part") or f.endswith(".ytdl")):
                os.remove(fp); logger.debug("Cleanedup: %s", f)
        except OSError: pass


def _run(args, timeout=240):
    cmd = [YT]
    if os.path.isfile(COOKIES_FILE): cmd.extend(["--cookies", COOKIES_FILE])
    cmd.extend(args)
    logger.info("CMD: %s", " ".join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired: return False, "", "TIMEOUT"
    except Exception as e: return False, "", str(e)


def _oembed(url):
    import requests; from config import HTTP_TIMEOUT
    try:
        r = requests.get("https://www.youtube.com/oembed", params={"url":url,"format":"json"}, headers={"User-Agent":"Mozilla/5.0 Chrome/125.0"}, timeout=HTTP_TIMEOUT)
        return r.json().get("title","Video") if r.status_code==200 else None
    except: return None


def get_video_info(url):
    t = _oembed(url)
    if t: return {"title":t, "duration":0,
        "formats":[
            {"format_id":"best","ext":"mp4","format_note":"Mejor calidad","resolution":"1080p"},
            {"format_id":"best[height<=720]","ext":"mp4","format_note":"HD 720p","resolution":"720p"},
            {"format_id":"worst","ext":"mp4","format_note":"Baja calidad","resolution":"360p"}]}
    return None


def validate_cookies():
    if not os.path.isfile(COOKIES_FILE): return False, "No hay cookies"
    ok, o, s = _run(["--simulate","--print","title","--format","best"]+SINGLE+["https://www.youtube.com/watch?v=jNQXAC9IVRw"], timeout=30)
    if any(x in s.lower() for x in ["no video formats","no supported javascript"]): logger.error("ENV ERROR"); return False, "ENV_ERROR"
    if "Sign in" in s: return False, "YOUTUBE_BLOCK"
    if ok and o.strip(): logger.info("Cookies OK"); return True, "OK"
    return False, s[:200] or "Error"


def download_video(url, format_id="best"):
    _cleanup_stale()
    uniq = uuid.uuid4().hex[:8]
    fmt_map = {"best":["best","bestvideo+bestaudio","best[ext=mp4]","18"],
               "best[height<=720]":["best[height<=720]","bestvideo[height<=720]+bestaudio","best","18"],
               "worst":["worst","18","best"]}
    last = ""
    for fmt in fmt_map.get(format_id, ["best","18"]):
        outtmpl = os.path.join(DOWNLOAD_DIR, f"yt_%(id)s_{uniq}.%(ext)s")
        args = ["--format",fmt,"--output",outtmpl] + BASE_OPTS + SINGLE + [url]
        ok, o, s = _run(args)
        if ok:
            for f in os.listdir(DOWNLOAD_DIR):
                if uniq in f and os.path.isfile(fp:=os.path.join(DOWNLOAD_DIR,f)) and os.path.getsize(fp)>1024:
                    sz = os.path.getsize(fp)//1024//1024
                    logger.info("OK: %s (%d MB)", f, sz); return fp, ""
        last = s or "Error"
        if "Requested format" not in s: continue
        last = "FORMATO_NO_DISPONIBLE"
    return None, last[:100]


def download_audio(url):
    _cleanup_stale()
    uniq = uuid.uuid4().hex[:8]
    outtmpl = os.path.join(DOWNLOAD_DIR, f"yt_%(id)s_{uniq}.%(ext)s")
    args = ["--format","bestaudio/best","--extract-audio","--audio-format","mp3","--output",outtmpl] + BASE_OPTS + SINGLE + [url]
    ok, o, s = _run(args)
    if ok:
        for f in os.listdir(DOWNLOAD_DIR):
            if uniq in f and f.endswith(".mp3") and os.path.getsize(fp:=os.path.join(DOWNLOAD_DIR,f))>1024:
                return fp, ""
    return None, s[:100] or "Error"