"""
Configuracion centralizada del bot descargador.
Carga variables de entorno y define constantes.
"""

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No se encontro BOT_TOKEN en las variables de entorno")

# Telegram Bot API caps file sends at 50MB for most file types.
# This is the pre-send check limit (hard stop before attempting upload).
MAX_FILE_SIZE = 50 * 1024 * 1024
DOWNLOAD_DIR = "downloads"

# Ruta compartida de cookies de YouTube
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

HTTP_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300

# --- Security / access control ---
# Comma-separated Telegram user IDs allowed to use the bot.
# If empty or not set, anyone can use the bot.
def _parse_int_list(val):
    if not val:
        return None
    try:
        return [int(x.strip()) for x in val.split(",") if x.strip()]
    except ValueError:
        return None

ALLOWED_USER_IDS = _parse_int_list(os.getenv("ALLOWED_USER_IDS"))

# Comma-separated Telegram user IDs allowed to upload cookies.
# If empty or not set, only ALLOWED_USER_IDS can upload (or anyone if that's open).
ADMIN_USER_IDS = _parse_int_list(os.getenv("ADMIN_USER_IDS"))
