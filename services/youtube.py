"""YouTube downloader - async-safe via subprocess."""

import os, json, subprocess, logging, uuid, re
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

NL = chr(10)


def _cleanup():
    if not os.path.isdir(DOWNLOAD_DIR): return
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".part") or f.endswith(".ytdl"):
            try: os.remove(os.path.join(DOWNLOAD_DIR, f))
            except OSError:
                pass


def _read_info(info_path: str) -> dict:
    try:
        with open(info_path) as f:
            data = json.load(f)
        resolution = data.get("resolution", "")
        display_res = resolution.replace("x", "\u00d7") if resolution else "HD"
        return {"resolution": display_res, "duration_sec": int(data.get("duration", 0) or 0)}
    except Exception:
        return {"resolution": "HD", "duration_sec": 0}


def _run(args, timeout=240, progress_callback=None, use_ejs=True):
    cmd = [YT, "--no-check-certificates", "--no-cache-dir", "--newline", "--progress"]
    if os.path.isfile(COOKIES_FILE):
        cmd.extend(["--cookies", COOKIES_FILE])
    if use_ejs:
        cmd.extend(EJS_FLAGS)
    cmd.extend(YT_EXTRACTOR)
    cmd.extend(args)
    try:
        if not progress_callback:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout.strip(), r.stderr.strip()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_content = []
        progress_re = re.compile(r"\[download\]\s+(\d+\.\d+)%")
        last_tenth = -1

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                stdout_content.append(line)
                m = progress_re.search(line)
                if m:
                    pct = int(float(m.group(1)))
                    if pct // 10 > last_tenth:
                        last_tenth = pct // 10
                        progress_callback(float(pct))

        _, stderr = process.communicate(timeout=timeout)
        return process.returncode == 0, "".join(stdout_content).strip(), stderr.strip()
    except Exception as e:
        return False, "", str(e)


# Extract YouTube video ID from various URL formats
_YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})",
    re.IGNORECASE,
)


def _get_yt_thumbnail(url: str) -> str | None:
    m = _YT_ID_RE.search(url)
    if m:
        return f"https://i.ytimg.com/vi/{m.group(1)}/hqdefault.jpg"
    return None


def get_video_info(url):
    import requests
    from config import HTTP_TIMEOUT
    try:
        r = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=HTTP_TIMEOUT)
        t = r.json().get("title", "Video") if r.status_code == 200 else "YouTube Video"
        return {"title": t}
    except Exception:
        return {"title": "YouTube Video"}


def _find_file(uniq, ext_filter=None):
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
        out = os.path.join(DOWNLOAD_DIR, "vert_{}.mp4".format(uuid.uuid4().hex[:8]))
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                           "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        w, h = map(int, r.stdout.strip().split(","))
        new_w = int(h * 9 / 16)
        new_w -= (new_w % 2)
        x_off = (w - new_w) // 2
        cmd = ["ffmpeg", "-y", "-nostdin", "-threads", "2", "-i", path,
               "-vf", "crop={}:{}:{}:0".format(new_w, h, x_off),
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
               "-c:a", "aac", "-b:a", "96k", out]
        if subprocess.run(cmd, timeout=300).returncode == 0:
            os.remove(path)
            return out
    except Exception as e:
        logger.debug("crop_vertical failed: %s", e)
    return None


FMT_SELECTOR = {
    "360": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
    "720": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
}


def download_video(url, format_id="360", progress_callback=None, start_time=None, end_time=None):
    _cleanup()
    uniq = uuid.uuid4().hex[:8]
    fmt = FMT_SELECTOR.get(format_id, FMT_SELECTOR["360"])
    extra = []
    if start_time and end_time:
        extra.extend(["--download-sections", "*{}-{}".format(start_time, end_time),
                      "--force-keyframes-at-cuts"])
    fp, meta = _try_download(uniq, [fmt], extra, progress_callback, url)
    if fp:
        if format_id == "vertical" or format_id == "720":
            v = _crop_vertical(fp)
            return (v, "", meta) if v else (fp, "", meta)
        return fp, "", meta
    return None, "Error", {}


def _try_download(uniq, formats, extra, progress_callback, url):
    for fmt in formats:
        o = os.path.join(DOWNLOAD_DIR, "yt_{}.%(ext)s".format(uniq))
        ok, sout, serr = _run(["--format", fmt, "--output", o] + BASE + SINGLE + extra + [url],
                              progress_callback=progress_callback, use_ejs=True)
        if ok:
            fp = _find_file(uniq)
            if fp:
                info_path = fp.rsplit(".", 1)[0] + ".info.json"
                meta = _read_info(info_path) if os.path.isfile(info_path) else {}
                return fp, meta
        logger.error("yt-dlp format '%s' FAILED. stderr:%s%s", fmt, NL, serr)
    return None, {}


def download_audio(url, progress_callback=None):
    _cleanup()
    uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, "audio_{}.%(ext)s".format(uniq))
    ok, sout, serr = _run(
        ["--format", "bestaudio[ext=m4a]/bestaudio/best", "--extract-audio",
         "--audio-format", "mp3", "--output", o] + BASE + SINGLE + [url],
        progress_callback=progress_callback, use_ejs=True)
    if ok:
        fp = _find_file(uniq, ext_filter=".mp3")
        if fp:
            return fp, ""
    logger.error("yt-dlp audio download FAILED. stderr:%s%s", NL, serr)
    return None, "Error"


def download_playlist_audio(url):
    _cleanup()
    uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, "pl_{}_%(playlist_index)s.%(ext)s".format(uniq))
    ok, sout, serr = _run(["--playlist-items", "1-10", "--extract-audio",
                          "--audio-format", "mp3", "--output", o] + BASE + [url],
                          timeout=600, use_ejs=True)
    files = sorted(os.listdir(DOWNLOAD_DIR))
    result = [os.path.join(DOWNLOAD_DIR, f) for f in files
              if "pl_{}_".format(uniq) in f and f.endswith(".mp3")]
    return result if result else None, "Error"


def validate_cookies():
    if not os.path.isfile(COOKIES_FILE):
        return False, "No hay cookies"
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    ok, o, s = _run(["--simulate", "--print", "title", "--format", "best"] + SINGLE + [test_url],
                    30, use_ejs=False)
    if "Sign in" in s or "sign in" in s.lower():
        for line in s.strip().split(NL):
            if "ERROR:" in line:
                return False, "YOUTUBE_BLOCK: " + line[:150]
        return False, "YOUTUBE_BLOCK: " + s[:200]
    if ok and o.strip():
        return True, "OK"
    logger.error("validate_cookies FAILED with yt-dlp stderr:%s%s", NL, s)
    return False, "ERROR: " + s[:300]
