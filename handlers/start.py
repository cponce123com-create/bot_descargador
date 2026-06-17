"""Handlers de comandos basicos."""

import os, logging
from telegram import Update
from telegram.ext import ContextTypes
from config import COOKIES_FILE
from services.youtube import validate_cookies
logger = logging.getLogger(__name__)

async def start(update, context):
    text = ("🎬 *Bot Descargador*" + chr(10) + chr(10)
        + "Envíame un enlace de **YouTube** o **TikTok** y lo descargo." + chr(10) + chr(10)
        + "Ejemplos:" + chr(10)
        + "• youtube.com/watch?v=..." + chr(10)
        + "• youtu.be/..." + chr(10)
        + "• tiktok.com/@user/video/..." + chr(10) + chr(10)
        + "/help para mas info. /cookies para enviar cookies.")
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update, context):
    text = ("📖 *Ayuda*" + chr(10) + chr(10)
        + "YouTube: envia URL, elige calidad o audio." + chr(10)
        + "TikTok: envia URL, descarga sin marca de agua." + chr(10)
        + "/cookies - enviar cookies de YouTube para evitar bloqueos." + chr(10)
        + "Limite: 300MB")
    await update.message.reply_text(text, parse_mode="Markdown")

async def cookies_command(update, context):
    if not update.message.document:
        text = ("🍪 *Cookies de YouTube*" + chr(10) + chr(10)
            + "Descarga la extension *Get cookies.txt* para Chrome/Firefox." + chr(10)
            + "Inicia sesion en YouTube, exporta cookies y envia el archivo con /cookies.")
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
        return
    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        await update.message.reply_text("❌ Envia un archivo .txt con las cookies.")
        return
    await update.message.reply_text("⏳ Guardando y validando cookies...")
    try:
        file = await doc.get_file()
        await file.download_to_drive(COOKIES_FILE)
        ok, msg = validate_cookies()
        if ok:
            await update.message.reply_text("✅ *Cookies OK* - Puedes descargar YouTube sin bloqueos.", parse_mode="Markdown")
            logger.info("Cookies guardadas y validadas: %s", msg)
        else:
            os.remove(COOKIES_FILE)
            await update.message.reply_text("❌ *Cookies invalidas:* " + msg, parse_mode="Markdown")
            logger.error("Cookies invalidas: %s", msg)
    except Exception as e:
        logger.error("Error cookies: %s", e)
        await update.message.reply_text("❌ Error al procesar. Intenta de nuevo.")