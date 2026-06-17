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

MAX_FILE_SIZE = 300 * 1024 * 1024
DOWNLOAD_DIR = "downloads"

# Ruta compartida de cookies de YouTube (usada por handlers/start.py y services/youtube.py)
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

YT_DLP_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
    "restrictfilenames": True,
}

HTTP_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300
