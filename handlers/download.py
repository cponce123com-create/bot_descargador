"""Handlers de descarga: detecta URLs, descarga y envia."""

import os, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_FILE_SIZE
from services.youtube import get_video_info, download_video, download_audio
from services.tiktok import download_tiktok_no_watermark
from services.file_utils import cleanup, cleanup_old_files

SELECTING_FORMAT = 1

YT_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE)
TT_RE = re.compile(r"(https?://)?(www\.)?(vm\.tiktok\.com|tiktok\.com)/", re.IGNORECASE)


def _error_msg(error):
    if "ENV_ERROR" in error: return "❌ Error temporal del servidor. Intenta mas tarde."
    if "YOUTUBE_BLOCK" in error: return "❌ YouTube bloquea la IP de Render. Usa /cookies para enviar cookies validas."
    if "VIDEO_PRIVADO" in error: return "❌ Este video es privado."
    if "VIDEO_NO_DISPONIBLE" in error: return "❌ Video no disponible (eliminado o restringido)."
    if "FORMATO_NO_DISPONIBLE" in error: return "❌ Formato no disponible para este video."
    if "ARCHIVO_MUY_GRANDE" in error: return "❌ El video excede 300MB. Prueba con audio."
    return "❌ Error: " + error[:100]


def detect_platform(url):
    if YT_RE.search(url): return "youtube"
    if TT_RE.search(url): return "tiktok"
    return None


async def handle_message(update, context):
    text = update.message.text.strip()
    plat = detect_platform(text)
    if not plat:
        await update.message.reply_text("❌ No reconozco la URL. Envia enlaces de YouTube o TikTok.")
        return ConversationHandler.END
    cleanup_old_files()
    if plat == "youtube": return await handle_youtube(update, context, text)
    return await handle_tiktok(update, context, text)


async def handle_youtube(update, context, url):
    s = await update.message.reply_text("⏳ Analizando...")
    info = get_video_info(url)
    if not info:
        await s.edit_text("❌ No pude obtener info. ¿URL valida?")
        return ConversationHandler.END
    context.user_data["yt_url"] = url
    t = info["title"][:50] + "..." if len(info["title"]) > 50 else info["title"]
    kb = [[InlineKeyboardButton("🎬 Mejor", callback_data="yt_best"),
          InlineKeyboardButton("📱 Mediano", callback_data="yt_medium")],
         [InlineKeyboardButton("🎵 Audio", callback_data="yt_audio")],
         [InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    await s.edit_text("📹 *" + t + "*" + chr(10) + "Selecciona:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT


async def handle_tiktok(update, context, url):
    s = await update.message.reply_text("⏳ Descargando TikTok...")
    path = download_tiktok_no_watermark(url)
    if not path:
        await s.edit_text("❌ No pude descargar. ¿Privado o eliminado?")
        return ConversationHandler.END
    if os.path.getsize(path) > MAX_FILE_SIZE:
        cleanup(path); await s.edit_text("❌ Video demasiado grande (max 300MB).")
        return ConversationHandler.END
    try:
        await s.edit_text("📤 Enviando...")
        with open(path, "rb") as f: await update.message.reply_video(f, caption="✅ Sin marca de agua", supports_streaming=True)
        await s.delete()
    except: await s.edit_text("❌ Error al enviar.")
    finally: cleanup(path)
    return ConversationHandler.END


async def format_callback(update, context):
    q = update.callback_query; await q.answer()
    choice = q.data; url = context.user_data.get("yt_url")
    if choice == "yt_cancel":
        await q.edit_message_text("✅ Cancelado.")
        return ConversationHandler.END
    if not url:
        await q.edit_message_text("❌ URL no encontrada.")
        return ConversationHandler.END
    await q.edit_message_text("⏳ Descargando...")
    fmt_map = {"yt_best": "best", "yt_medium": "best[height<=720]"}
    if choice == "yt_audio": path, error = download_audio(url)
    else: path, error = download_video(url, fmt_map.get(choice, "best"))
    if not path:
        await q.edit_message_text(_error_msg(error))
        return ConversationHandler.END
    if os.path.getsize(path) > MAX_FILE_SIZE:
        cleanup(path); await q.edit_message_text("❌ Archivo >300MB.")
        return ConversationHandler.END
    try:
        await q.edit_message_text("📤 Enviando...")
        if choice == "yt_audio":
            with open(path, "rb") as f: await q.message.reply_audio(f, caption="✅ Audio")
        else:
            with open(path, "rb") as f: await q.message.reply_video(f, caption="✅ Video", supports_streaming=True)
        await q.delete_message()
    except: await q.edit_message_text("❌ Error al enviar.")
    finally: cleanup(path)
    return ConversationHandler.END


async def cancel(update, context):
    await update.message.reply_text("✅ Cancelado.")
    return ConversationHandler.END