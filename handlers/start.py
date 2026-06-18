"""Handlers basicos."""

import os, logging, asyncio
from telegram import Update
from telegram.ext import ContextTypes
from config import COOKIES_FILE
logger = logging.getLogger(__name__)

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
+ "*Instagram:* envia URL de Reels o Posts." + chr(10) + chr(10)
        + "/cookies - cookies de YouTube (opcional)" + chr(10)
        + "Limite: 300MB por archivo")
    await up.message.reply_text(text, parse_mode="Markdown")

async def cookies_command(up, ctx):
    from services.youtube import validate_cookies
    if not up.message.document:
        t = ("🍪 *Cookies*" + chr(10) + chr(10)
            + "Si YouTube bloquea, exporta cookies con *Get cookies.txt*" + chr(10)
            + "y envialas con /cookies.")
        await up.message.reply_text(t, parse_mode="Markdown", disable_web_page_preview=True)
        return
    doc = up.message.document
    if not doc.file_name.endswith(".txt"): await up.message.reply_text("❌ Archivo .txt."); return
    await up.message.reply_text("⏳ Validando cookies...")
    try:
        f = await doc.get_file(); await f.download_to_drive(COOKIES_FILE)
        ok, msg = await asyncio.to_thread(validate_cookies)
        if ok: await up.message.reply_text("✅ *Cookies OK.*", parse_mode="Markdown")
        elif "ENV_ERROR" in msg: await up.message.reply_text("❌ Error del servidor."); logger.error("ENV_ERROR")
        else: os.remove(COOKIES_FILE); await up.message.reply_text("❌ Cookies invalidas: " + msg)
    except Exception as e: logger.error("Error cookies: %s", e); await up.message.reply_text("❌ Error.")