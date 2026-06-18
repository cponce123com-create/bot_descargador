"""YouTube downloader - async-safe via subprocess."""

import os, json, subprocess, logging, uuid
from config import DOWNLOAD_DIR, COOKIES_FILE
logger = logging.getLogger(__name__); YT = "yt-dlp"

SINGLE = ["--no-playlist", "--playlist-end", "1"]

EJS_FLAGS = [
    "--js-runtimes", "node",
    "--js-runtimes", "deno",
    "--remote-components", "ejs:npm",
]

YT_EXTRACTOR = ["--extractor-args", "youtube:player_client=android,web"]

BASE = [
    "--no-warnings", "--quiet", "--no-mtime",
    "--force-overwrites", "--max-filesize", "2G",
    "--merge-output-format", "mp4",
    "--concurrent-fragments", "5", "--buffer-size", "16K",
    "--no-playlist",
    "--write-info-json",
]


def _cleanup():
    if not os.path.isdir(DOWNLOAD_DIR): return
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".part") or f.endswith(".ytdl"):
            try: os.remove(os.path.join(DOWNLOAD_DIR, f))
            except: pass


def _read_info(info_path: str) -> dict:
    """Read .info.json written by yt-dlp and return useful metadata."""
    try:
        with open(info_path) as f:
            data = json.load(f)
        resolution = data.get("resolution", "")
        duration = data.get("duration", 0)
        display_res = resolution.replace("x", "×") if resolution else "HD"
        return {
            "resolution": display_res,
            "duration_sec": int(duration) if duration else 0,
            "extractor": data.get("extractor", ""),
            "id": data.get("id", ""),
        }
    except Exception:
        return {"resolution": "HD", "duration_sec": 0, "extractor": "", "id": ""}


def _run(args, timeout=240, progress_callback=None):
    cmd = [YT, "--no-check-certificates", "--no-cache-dir", "--newline", "--progress"]
    if os.path.isfile(COOKIES_FILE):
        cmd.extend(["--cookies", COOKIES_FILE])
    cmd.extend(EJS_FLAGS)
    cmd.extend(YT_EXTRACTOR)
    cmd.extend(args)
    try:
        if not progress_callback:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout.strip(), r.stderr.strip()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_content = []
        import re
        progress_re = re.compile(r"\[download\]\s+(\d+\.\d+)%")
        last_percent = -1

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
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
    except Exception as e:
        return False, "", str(e)


def get_video_info(url):
    import requests;
    from config import HTTP_TIMEOUT
    try:
        r = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=HTTP_TIMEOUT)
        t = r.json().get("title", "Video") if r.status_code == 200 else "YouTube Video"
        return {"title": t}
    except:
        return {"title": "YouTube Video"}


def _find_file(uniq, ext_filter=None):
    """Find a downloaded file by unique ID, optionally filtering by extension."""
    for fn in os.listdir(DOWNLOAD_DIR):
        if uniq in fn and os.path.isfile(fp := os.path.join(DOWNLOAD_DIR, fn)):
            if ext_filter and not fn.endswith(ext_filter):
                continue
            if ext_filter is None and fn.endswith(".info.json"):
                continue
            return fp
    return None


def _crop_vertical(path):
    try:
        out = os.path.join(DOWNLOAD_DIR, f"vert_{uuid.uuid4().hex[:8]}.mp4")
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        w, h = map(int, r.stdout.strip().split(","))
        new_w = int(h * 9 / 16);
        new_w -= (new_w % 2)
        x_off = (w - new_w) // 2
        cmd = ["ffmpeg", "-y", "-nostdin", "-threads", "2", "-i", path, "-vf", f"crop={new_w}:{h}:{x_off}:0", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", out]
        if subprocess.run(cmd, timeout=300).returncode == 0:
            os.remove(path);
            return out
    except:
        pass
    return None


def download_video(url, format_id="360", progress_callback=None, start_time=None, end_time=None):
    _cleanup();
    uniq = uuid.uuid4().hex[:8]
    fmt = "bv*[ext=mp4][filesize<2G]+ba[ext=m4a][filesize<2G]/bv*[ext=mp4]+ba[ext=m4a]/best[filesize<2G]/best"
    extra = []
    if start_time and end_time:
        extra.extend(["--download-sections", f"*{start_time}-{end_time}", "--force-keyframes-at-cuts"])
    fp, meta = _try_download(uniq, [fmt], extra, progress_callback, url)
    if fp:
        if format_id == "vertical":
            v = _crop_vertical(fp)
            return (v, "") if v else (fp, "")
        return fp, "", meta
    return None, "Error", {}


def _try_download(uniq, formats, extra, progress_callback, url):
    nl = chr(10)
    for fmt in formats:
        o = os.path.join(DOWNLOAD_DIR, f"yt_{uniq}.%(ext)s")
        ok, sout, serr = _run(["--format", fmt, "--output", o] + BASE + SINGLE + extra + [url], progress_callback=progress_callback)
        if ok:
            fp = _find_file(uniq)
            if fp:
                info_path = fp.rsplit(".", 1)[0] + ".info.json"
                meta = _read_info(info_path) if os.path.isfile(info_path) else {}
                return fp, meta
        logger.error("yt-dlp format '%s' FAILED. stderr:%s%s", fmt, nl, serr)
    return None, {}


def download_audio(url, progress_callback=None):
    nl = chr(10)
    _cleanup();
    uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"audio_{uniq}.%(ext)s")
    ok, sout, serr = _run(
        ["--format", "bestaudio[ext=m4a]/bestaudio/best", "--extract-audio", "--audio-format", "mp3", "--output", o] + BASE + SINGLE + [url],
        progress_callback=progress_callback)
    if ok:
        fp = _find_file(uniq, ext_filter=".mp3")
        if fp:
            return fp, ""
    logger.error("yt-dlp audio download FAILED. stderr:%s%s", nl, serr)
    return None, "Error"


def download_playlist_audio(url):
    _cleanup();
    uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"pl_{uniq}_%(playlist_index)s.%(ext)s")
    ok, sout, serr = _run(["--playlist-items", "1-10", "--extract-audio", "--audio-format", "mp3", "--output", o] + BASE + [url], timeout=600)
    files = [os.path.join(DOWNLOAD_DIR, f) for f in sorted(os.listdir(DOWNLOAD_DIR)) if f"pl_{uniq}_" in f and f.endswith(".mp3")]
    return files if files else None, "Error"


def validate_cookies():
    """Validate cookies and return a user-friendly message."""
    if not os.path.isfile(COOKIES_FILE):
        return False, "No hay cookies"
    ok, o, s = _run(["--simulate", "--print", "title", "--format", "best"] + SINGLE + ["https://www.youtube.com/watch?v=jNQXAC9IVRw"], 30)
    if "Sign in" in s or "sign in" in s.lower():
        lines = s.strip().split("\n")
        # Return only the actual error line, not warnings
        errors = [l for l in lines if "ERROR:" in l]
        detail = errors[0] if errors else s[:200]
        return False, "YOUTUBE_BLOCK: " + detail[:150]
    if ok and o.strip():
        return True, "OK"
    nl = chr(10)
    logger.error("validate_cookies FAILED with yt-dlp stderr:%s%s", nl, s)
    return False, "ERROR: " + s[:300]
