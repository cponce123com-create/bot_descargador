"""
Utilidades para manejo de archivos.
"""

import os
import re
import time


def sanitize_filename(filename, max_length=100):
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    name = name.strip("._")
    if not name:
        name = "video"
    max_name_len = max_length - len(ext) - 1
    if len(name) > max_name_len:
        name = name[:max_name_len]
    return f"{name}{ext}"


def cleanup(filepath):
    if filepath and os.path.isfile(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass


def cleanup_old_files(max_age_seconds=3600):
    count = 0
    if not os.path.isdir("downloads"):
        return 0
    now = time.time()
    for fname in os.listdir("downloads"):
        fpath = os.path.join("downloads", fname)
        if os.path.isfile(fpath):
            try:
                if os.path.getmtime(fpath) < now - max_age_seconds:
                    os.remove(fpath)
                    count += 1
            except OSError:
                pass
    return count
