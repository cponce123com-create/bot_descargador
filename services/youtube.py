"""YouTube downloader - async-safe via subprocess."""

import os, subprocess, logging, uuid
from config import DOWNLOAD_DIR, COOKIES_FILE
logger = logging.getLogger(__name__); YT = "yt-dlp"

SINGLE = ["--no-playlist","--playlist-end","1"]
BASE = ["--no-warnings","--quiet","--no-mtime","--force-overwrites","--max-filesize","300M","--merge-output-format","mp4"]

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
        r = subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        return r.returncode==0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired: return False,"","TIMEOUT"
    except Exception as e: return False,"",str(e)

def _oembed(url):
    import requests; from config import HTTP_TIMEOUT
    try:
        r = requests.get("https://www.youtube.com/oembed",params={"url":url,"format":"json"},headers={"User-Agent":"Mozilla/5.0 Chrome/125.0"},timeout=HTTP_TIMEOUT)
        return r.json().get("title","Video") if r.status_code==200 else None
    except: return None

def get_video_info(url):
    t = _oembed(url)
    if t: return {"title":t,"duration":0,"formats":[{"format_id":"360","ext":"mp4","format_note":"Video","resolution":"360p"},{"format_id":"vertical","ext":"mp4","format_note":"Vertical","resolution":"9:16"}]}
    return None

def validate_cookies():
    if not os.path.isfile(COOKIES_FILE): return False,"No hay cookies"
    ok,o,s = _run(["--simulate","--print","title","--format","best"]+SINGLE+["https://www.youtube.com/watch?v=jNQXAC9IVRw"],30)
    if any(x in s.lower() for x in ["no video formats","no supported javascript"]): logger.error("ENV ERROR"); return False,"ENV_ERROR"
    if "Sign in" in s: return False,"YOUTUBE_BLOCK"
    if ok and o.strip(): return True,"OK"
    return False,s[:200] or "Error"

def _crop_vertical(path):
    try:
        out = os.path.join(DOWNLOAD_DIR, f"vert_{uuid.uuid4().hex[:8]}.mp4")
        r = subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                          "-show_entries","stream=width,height","-of","csv=p=0",path],
                          capture_output=True,text=True,timeout=30)
        if r.returncode!=0 or not r.stdout.strip():
            logger.warning("ffprobe fail: %s",r.stderr[:100]); return None
        parts = r.stdout.strip().split(",")
        if len(parts)!=2: return None
        w, h = int(parts[0]), int(parts[1])
        new_w = int(h * 9 / 16)
        if new_w > w:
            new_w = w; new_h = int(w * 16 / 9); y_off = (h - new_h) // 2; x_off = 0
        else:
            new_h = h; x_off = (w - new_w) // 2; y_off = 0
        new_w = new_w - (new_w % 2)  # Asegurar par
        if new_w < 2: new_w = 2
        cmd = ["ffmpeg","-y","-nostdin","-i",path,"-vf",f"crop={new_w}:{new_h}:{x_off}:{y_off}",
               "-c:v","mpeg4","-qscale:v","3","-c:a","aac","-b:a","64k",out]
        logger.info("Cropping %dx%d -> %dx%d (ultrafast)",w,h,new_w,new_h)
        r = subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        if r.returncode==0 and os.path.isfile(out) and os.path.getsize(out)>1024:
            os.remove(path); logger.info("Vertical crop OK"); return out
        logger.warning("ffmpeg fail: %s",r.stderr[:200])
    except Exception as e:
        logger.error("Crop exception: %s",e)
    return None
    """Cropea video a formato vertical 9:16 centrado usando ffmpeg."""
    out = os.path.join(DOWNLOAD_DIR, f"vert_{uuid.uuid4().hex[:8]}.mp4")
    # Obtener dimensiones
    r = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0",path],
                      capture_output=True,text=True,timeout=15)
    if r.returncode!=0: return None
    parts = r.stdout.strip().split(",")
    if len(parts)!=2: return None
    w, h = int(parts[0]), int(parts[1])
    # Calcular crop para 9:16 (vertical)
    new_w = int(h * 9 / 16)
    if new_w > w: new_w = w; new_h = int(w * 16 / 9); y_off = (h - new_h) // 2; x_off = 0
    else: new_h = h; x_off = (w - new_w) // 2; y_off = 0
    cmd = ["ffmpeg","-y","-i",path,"-vf",f"crop={new_w}:{new_h}:{x_off}:{y_off}","-c:a","copy",out]
    r = subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    if r.returncode==0 and os.path.isfile(out) and os.path.getsize(out)>1024:
        os.remove(path); return out
    return None

def download_video(url, format_id="360"):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    if format_id=="vertical":
        f = ["best[height<=360]","bestvideo[height<=360]+bestaudio","worst","18","best"]
    else:
        f = ["best[height<=360]","bestvideo[height<=360]+bestaudio","worst","18","best"]
    last = ""
    for fmt in f:
        o = os.path.join(DOWNLOAD_DIR,f"yt_%(id)s_{uniq}.%(ext)s")
        ok,sout,serr = _run(["--format",fmt,"--output",o] + BASE + SINGLE + [url])
        if ok:
            for fn in os.listdir(DOWNLOAD_DIR):
                if uniq in fn and os.path.isfile(fp:=os.path.join(DOWNLOAD_DIR,fn)) and os.path.getsize(fp)>1024:
                    sz = os.path.getsize(fp)//1024//1024; logger.info("Descargado: %s (%d MB)",fn,sz)
                    if format_id=="vertical":
                        v = _crop_vertical(fp)
                        if v: logger.info("Vertical OK: %s",v); return v,""
                        logger.warning("Crop fallo, enviando original"); return fp,""
                    return fp,""
        last = serr[:100] or "Error"
        if "Requested format" not in serr: continue
        last = "FORMATO_NO_DISPONIBLE"
    return None,last

def download_audio(url):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR,f"yt_%(id)s_{uniq}.%(ext)s")
    ok,sout,serr = _run(["--format","bestaudio/best","--extract-audio","--audio-format","mp3","--output",o] + BASE + SINGLE + [url])
    if ok:
        for fn in os.listdir(DOWNLOAD_DIR):
            if uniq in fn and fn.endswith(".mp3") and os.path.getsize(fp:=os.path.join(DOWNLOAD_DIR,fn))>1024:
                return fp,""
    return None,serr[:100] or "Error"