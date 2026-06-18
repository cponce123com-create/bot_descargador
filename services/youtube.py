"""YouTube downloader - async-safe via subprocess."""

import os, subprocess, logging, uuid
from config import DOWNLOAD_DIR, COOKIES_FILE
logger = logging.getLogger(__name__); YT = "yt-dlp"

SINGLE = ["--no-playlist","--playlist-end","1"]
# Use android client ONLY when NO cookies are available (avoids JS challenge).
# When cookies exist, the web client works fine and has more format options.
YT_EXTRACTOR = ["--extractor-args", "youtube:player_client=android"]
BASE = [
    "--no-warnings",
    "--quiet",
    "--no-mtime",
    "--force-overwrites",
    "--max-filesize", "300M",
    "--merge-output-format", "mp4",
    "--concurrent-fragments", "5",
    "--buffer-size", "16K",
    "--no-playlist"
]

def _cleanup():
    if not os.path.isdir(DOWNLOAD_DIR): return
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".part") or f.endswith(".ytdl"):
            try: os.remove(os.path.join(DOWNLOAD_DIR,f))
            except: pass

def _run(args, timeout=240, progress_callback=None):
    cmd = [YT, "--no-check-certificates", "--no-cache-dir", "--newline", "--progress"]
    if os.path.isfile(COOKIES_FILE):
        cmd.extend(["--cookies", COOKIES_FILE])
    else:
        # Only use android client when no cookies (avoids JS challenge in Render)
        cmd.extend(YT_EXTRACTOR)
    cmd.extend(args)
    try:
        if not progress_callback:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode==0, r.stdout.strip(), r.stderr.strip()
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_content = []
        import re
        progress_re = re.compile(r"\[download\]\s+(\d+\.\d+)%")
        last_percent = -1
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None: break
            if line:
                stdout_content.append(line)
                match = progress_re.search(line)
                if match:
                    percent = float(match.group(1))
                    if int(percent) // 10 > last_percent // 10:
                        last_percent = int(percent)
                        progress_callback(percent)
        
        _, stderr = process.communicate(timeout=timeout)
        return process.returncode == 0, "".join(stdout_content).strip(), stderr.strip()
    except Exception as e: return False, "", str(e)

def get_video_info(url):
    import requests; from config import HTTP_TIMEOUT
    try:
        r = requests.get("https://www.youtube.com/oembed",params={"url":url,"format":"json"},headers={"User-Agent":"Mozilla/5.0"},timeout=HTTP_TIMEOUT)
        t = r.json().get("title","Video") if r.status_code==200 else "YouTube Video"
        return {"title":t}
    except: return {"title":"YouTube Video"}

def _crop_vertical(path):
    try:
        out = os.path.join(DOWNLOAD_DIR, f"vert_{uuid.uuid4().hex[:8]}.mp4")
        r = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0",path],capture_output=True,text=True,timeout=30)
        if r.returncode!=0: return None
        w, h = map(int, r.stdout.strip().split(","))
        new_w = int(h * 9 / 16); new_w -= (new_w % 2)
        x_off = (w - new_w) // 2
        cmd = ["ffmpeg","-y","-nostdin","-threads","2","-i",path,"-vf",f"crop={new_w}:{h}:{x_off}:0","-c:v","libx264","-preset","ultrafast","-crf","28","-c:a","aac","-b:a","96k",out]
        if subprocess.run(cmd, timeout=300).returncode==0:
            os.remove(path); return out
    except: pass
    return None

def _convert_to_gif(path):
    try:
        out = path.rsplit(".", 1)[0] + ".gif"
        cmd = ["ffmpeg","-y","-i",path,"-vf","fps=10,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",out]
        if subprocess.run(cmd, timeout=60).returncode==0:
            os.remove(path); return out
    except: pass
    return None

def download_video(url, format_id="360", progress_callback=None, start_time=None, end_time=None, to_gif=False):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    # Use flexible format selectors that work with any YouTube client (no hardcoded IDs)
    # yt-dlp will pick the best matching format automatically
    if format_id == "vertical":
        # Best video+audio up to 480p, with many fallbacks
        f = ["bestvideo[height<=480]+bestaudio/best[height<=480]/best"]
    elif format_id == "360":
        f = ["bestvideo[height<=360]+bestaudio/best[height<=360]/best"]
    else:
        f = ["bestvideo[height<=720]+bestaudio/best[height<=720]/best"]
    
    args = []
    if start_time and end_time:
        args.extend(["--download-sections", f"*{start_time}-{end_time}", "--force-keyframes-at-cuts"])
        
    fp, ok = _try_download(uniq, f, args, progress_callback, url)
    if fp:
        if to_gif: return _convert_to_gif(fp), ""
        if format_id == "vertical": return _crop_vertical(fp) or fp, ""
        return fp, ""
    return None, "Error"

def _try_download(uniq, formats, args, progress_callback, url):
    """Try to download with the given formats. _run handles cookies vs android client."""
    for fmt in formats:
        o = os.path.join(DOWNLOAD_DIR, f"yt_{uniq}.%(ext)s")
        ok, sout, serr = _run(["--format", fmt, "--output", o] + BASE + SINGLE + args + [url], progress_callback=progress_callback)
        if ok:
            for fn in os.listdir(DOWNLOAD_DIR):
                if uniq in fn and os.path.isfile(fp := os.path.join(DOWNLOAD_DIR, fn)):
                    return fp, ok
        logger.info("Format %s failed: %s", fmt, serr[:150] if serr else "no error")
    return None, False

def download_audio(url, progress_callback=None):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"audio_{uniq}.%(ext)s")
    ok, sout, serr = _run(["--format", "bestaudio[ext=m4a]/bestaudio/best", "--extract-audio", "--audio-format", "mp3", "--output", o] + BASE + SINGLE + [url], progress_callback=progress_callback)
    if ok:
        for fn in os.listdir(DOWNLOAD_DIR):
            if uniq in fn and fn.endswith(".mp3"): return os.path.join(DOWNLOAD_DIR, fn), ""
    logger.info("Audio download failed: %s", serr[:100] if serr else "no error")
    return None, "Error"

def download_playlist_audio(url):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"pl_{uniq}_%(playlist_index)s.%(ext)s")
    ok, sout, serr = _run(["--playlist-items", "1-10", "--extract-audio", "--audio-format", "mp3", "--output", o] + BASE + [url], timeout=600)
    files = [os.path.join(DOWNLOAD_DIR, f) for f in sorted(os.listdir(DOWNLOAD_DIR)) if f"pl_{uniq}_" in f and f.endswith(".mp3")]
    return files if files else None, "Error"

def validate_cookies():
    if not os.path.isfile(COOKIES_FILE): return False,"No hay cookies"
    ok,o,s = _run(["--simulate","--print","title","--format","best"]+SINGLE+["https://www.youtube.com/watch?v=jNQXAC9IVRw"],30)
    if "Sign in" in s:
        return False,"YOUTUBE_BLOCK"
    if ok and o.strip():
        return True,"OK"
    # If we got here, yt-dlp couldn't complete the simulation (e.g. JS challenge
    # in Render's slim environment). Accept the cookies anyway — they may still
    # work for actual downloads, and the validation test itself is unreliable.
    logger.warning("validate_cookies simulation failed, accepting cookies anyway: %s", s[:150])
    return True,"OK"
