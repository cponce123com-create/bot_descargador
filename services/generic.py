"""Generic downloader for X, Pinterest, Reddit, etc. - async-safe via subprocess."""

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

def get_info(url):
    # Obtener título y miniatura
    ok, o, s = _run(["--get-title", "--get-thumbnail", url], 30)
    if ok:
        lines = o.split('\n')
        title = lines[0] if len(lines) > 0 else "Video"
        thumb = lines[1] if len(lines) > 1 else None
        return {"title": title, "thumbnail": thumb}
    return {"title": "Video", "thumbnail": None}

def download_generic(url, platform_name="Video", progress_callback=None):
    _cleanup(); uniq = uuid.uuid4().hex[:8]
    o = os.path.join(DOWNLOAD_DIR, f"{platform_name.lower()}_{uniq}.%(ext)s")

    download_args = ["--format", "best", "--output", o] + BASE + [url]
    if progress_callback:
        ok, sout, serr = _run_with_progress(download_args, progress_callback)
    else:
        ok, sout, serr = _run(download_args)

    if ok:
        for fn in os.listdir(DOWNLOAD_DIR):
            if uniq in fn and os.path.isfile(fp := os.path.join(DOWNLOAD_DIR, fn)) and os.path.getsize(fp) > 1024:
                return fp, ""

    return None, serr[:100] or "Error"


def _run_with_progress(args, progress_callback, timeout=240):
    """Run yt-dlp with real-time progress callback."""
    import re
    cmd = [YT]
    if os.path.isfile(COOKIES_FILE): cmd.extend(["--cookies", COOKIES_FILE])
    cmd.extend(["--newline", "--progress"])
    cmd.extend(args)
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_content = []
        progress_re = re.compile(r"\[download\]\s+(\d+\.?\d*)%")
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
                        progress_callback(pct)

        _, stderr = process.communicate(timeout=timeout)
        return process.returncode == 0, "".join(stdout_content).strip(), stderr.strip()
    except Exception as e:
        logger.warning("Progress download error: %s", e)
        return False, "", str(e)
