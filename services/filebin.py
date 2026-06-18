"""Filebin.net uploader for files that exceed Telegram's 50MB limit.

When a downloaded video is too large to send via Telegram (over 50MB),
we upload it to filebin.net and send a download link instead.
filebin.net is a free, no-auth file hosting service.
Files expire after approximately 7 days of inactivity.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

BIN_URL = "https://filebin.net"


def upload(path: str) -> str | None:
    """Upload a file to filebin.net and return its direct download URL.

    Returns the URL string on success, or None on failure.
    """
    if not os.path.isfile(path):
        logger.error("File not found for upload: %s", path)
        return None

    filename = os.path.basename(path)
    try:
        with open(path, "rb") as fp:
            r = requests.post(
                f"{BIN_URL}/{filename}",
                files={"file": (filename, fp)},
                timeout=300,
            )
        if r.status_code in (200, 201):
            data = r.json()
            # response structure: { "bin": { "id": "...", "url": "..." }, "file": { ... } }
            bin_id = data.get("bin", {}).get("id") or data.get("bin", {}).get("name", "")
            if bin_id:
                return f"{BIN_URL}/{bin_id}/{filename}"
        logger.warning("filebin upload failed: HTTP %d %s", r.status_code, r.text[:200])
    except requests.RequestException as e:
        logger.warning("filebin upload error: %s", e)
    return None
