"""Handlers basicos."""

import os, logging, asyncio
from telegram import Update
from telegram.ext import ContextTypes
from config import COOKIES_FILE, ADMIN_USER_IDS, ALLOWED_USER_IDS
logger = logging.getLogger(__name__)

def _is_admin(up: Update) -> bool:
    """Check if the user is allowed to upload cookies."""
    uid = up.effective_user.id if up.effective_user else None
    if not uid:
        return False
    if ADMIN_USER_IDS is not None:
        return uid in ADMIN_USER_IDS
    if ALLOWED_USER_IDS is not None:
        return uid in ALLOWED_USER_IDS
    return True  # no restrictions set

async def start(up, ctx):
    text = ("🎬 *Bot Descargador*" + chr(10) + chr(10)
        + "Envia enlace de **YouTube**, **TikTok**, **Facebook** o **Instagram**." + chr(10) + chr(10)
        + "/help | /cookies")
    await up.message.reply_text(text, parse_mode="Markdown")

async def help_command(up, ctx):
    text = ("📖 *Ayuda*" + chr(10) + chr(10)
        + "*YouTube:* envia URL, elige calidad:" + chr(10)
        + "🎬 Mejor - calidad maxima" + chr(10)
        + "📱 480p - peso moderado" + chr(10)
        + "🎵 Audio - solo MP3" + chr(10)
        + "*TikTok:* envia URL, descarga sin marca de agua." + chr(10)
+ "*Facebook:* envia URL para descargar videos o reels." + chr(10)
+ "*Instagram:* Reels o Posts." + chr(10)
+ "*X/Twitter, Reddit, Pinterest:* envia URL del video." + chr(10) + chr(10)
+ "*Recorte:* Envia `00:10-00:20` junto al link para recortar." + chr(10) + chr(10)
        + "/cookies - cookies de YouTube (opcional)" + chr(10)
        + "Limite: 50MB por archivo")
    await up.message.reply_text(text, parse_mode="Markdown")

async def cookies_command(up, ctx):
    from services.youtube import validate_cookies

    if not _is_admin(up):
        await up.message.reply_text("❌ Solo el admin puede cargar cookies.")
        return

    if not up.message.document:
        t = ("🍪 *Cookies*" + chr(10) + chr(10)
            + "Si YouTube bloquea, exporta cookies con *Get cookies.txt*" + chr(10)
            + "y envialas con /cookies.")
        await up.message.reply_text(t, parse_mode="Markdown", disable_web_page_preview=True)
        return
    doc = up.message.document
    if not doc.file_name.endswith(".txt"):
        await up.message.reply_text("❌ Archivo .txt.")
        return
    await up.message.reply_text("⏳ Validando cookies...")
    tmp_path = COOKIES_FILE + ".tmp"
    try:
        f = await doc.get_file()
        await f.download_to_drive(tmp_path)
        # Validate against the temp file by temporarily placing it at COOKIES_FILE
        if os.path.isfile(COOKIES_FILE):
            os.rename(COOKIES_FILE, COOKIES_FILE + ".bak")
            backup_exists = True
        else:
            backup_exists = False
        os.replace(tmp_path, COOKIES_FILE)
        ok, msg = await asyncio.to_thread(validate_cookies)
        if ok:
            # Remove backup, keep new cookies
            if backup_exists:
                try: os.remove(COOKIES_FILE + ".bak")
                except OSError: pass
            await up.message.reply_text("✅ *Cookies OK.*", parse_mode="Markdown")
        else:
            # Restore backup
            if backup_exists:
                os.replace(COOKIES_FILE + ".bak", COOKIES_FILE)
            else:
                try: os.remove(COOKIES_FILE)
                except OSError: pass
            err_display = msg[:200]
            await up.message.reply_text(f"❌ Cookies invalidas: {err_display}", parse_mode="Markdown")
    except Exception as e:
        logger.error("Error cookies: %s", e)
        # Cleanup tmp if it exists
        if os.path.isfile(tmp_path):
            try: os.remove(tmp_path)
            except OSError: pass
        await up.message.reply_text("❌ Error al procesar cookies.")
