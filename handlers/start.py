"""Handlers basicos."""

import os, logging, asyncio
from telegram import Update
from telegram.ext import ContextTypes
from config import COOKIES_FILE
logger = logging.getLogger(__name__)

async def start(up, ctx):
    text = ("🎬 *Bot Descargador*" + chr(10) + chr(10)
        + "Envia enlace de **YouTube** o **TikTok**." + chr(10) + chr(10)
        + "/help | /cookies")
    await up.message.reply_text(text, parse_mode="Markdown")

async def help_command(up, ctx):
    text = ("📖 *Ayuda*" + chr(10) + chr(10)
        + "YouTube: URL, elige calidad/audio." + chr(10)
        + "TikTok: URL, sin marca de agua." + chr(10)
        + "/cookies - cookies de YouTube." + chr(10)
        + "Limite: 300MB")
    await up.message.reply_text(text, parse_mode="Markdown")

async def cookies_command(up, ctx):
    from services.youtube import validate_cookies
    if not up.message.document:
        t = ("🍪 *Cookies*" + chr(10) + chr(10)
            + "Descarga *Get cookies.txt* para Chrome/Firefox." + chr(10)
            + "Login en YouTube, exporta y envia con /cookies.")
        await up.message.reply_text(t, parse_mode="Markdown", disable_web_page_preview=True)
        return
    doc = up.message.document
    if not doc.file_name.endswith(".txt"):
        await up.message.reply_text("❌ Archivo .txt requerido."); return
    await up.message.reply_text("⏳ Validando cookies...")
    try:
        f = await doc.get_file(); await f.download_to_drive(COOKIES_FILE)
        ok, msg = await asyncio.to_thread(validate_cookies)
        if ok:
            await up.message.reply_text("✅ *Cookies OK.* Ya puedes descargar YouTube.", parse_mode="Markdown")
        elif "ENV_ERROR" in msg:
            await up.message.reply_text("❌ Error del servidor. Contacta al admin.")
            logger.error("ENV_ERROR: %s", msg)
        else:
            os.remove(COOKIES_FILE)
            await up.message.reply_text("❌ Cookies invalidas: " + msg)
    except Exception as e:
        logger.error("Error cookies: %s", e)
        await up.message.reply_text("❌ Error al procesar.")