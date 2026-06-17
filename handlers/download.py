"""
Handlers de descarga: detecta URLs, menu de formatos, descarga y envio.
"""

import os
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import MAX_FILE_SIZE
from services.youtube import get_video_info, download_video, download_audio
from services.tiktok import download_tiktok_no_watermark
from services.file_utils import cleanup, cleanup_old_files

SELECTING_FORMAT = 1

YOUTUBE_PATTERN = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE)
TIKTOK_PATTERN = re.compile(r"(https?://)?(www\.)?(vm\.tiktok\.com|tiktok\.com)/", re.IGNORECASE)


def detect_platform(url):
    if YOUTUBE_PATTERN.search(url): return "youtube"
    if TIKTOK_PATTERN.search(url): return "tiktok"
    return None


async def handle_message(update, context):
    text = update.message.text.strip()
    plat = detect_platform(text)
    if not plat:
        await update.message.reply_text("\u274c No reconozco esa URL.\nEnv\u00eda un enlace de **YouTube** o **TikTok**.", parse_mode="Markdown")
        return ConversationHandler.END
    cleanup_old_files()
    if plat == "youtube": return await handle_youtube(update, context, text)
    return await handle_tiktok(update, context, text)


async def handle_youtube(update, context, url):
    status = await update.message.reply_text("\u23f3 Analizando video de YouTube...")
    info = get_video_info(url)
    if not info:
        await status.edit_text("\u274c No pude obtener informacion.\nVerifica que la URL sea valida y el video sea publico.")
        return ConversationHandler.END
    context.user_data["youtube_url"] = url
    title = (info["title"][:50] + "...") if len(info["title"]) > 50 else info["title"]
    mins = info["duration"] // 60 if info["duration"] else 0
    kb = [
        [InlineKeyboardButton("\U0001f3ac Mejor video", callback_data="yt_best"), InlineKeyboardButton("\U0001f4f1 Mediano", callback_data="yt_medium")],
        [InlineKeyboardButton("\U0001f3b5 Solo audio", callback_data="yt_audio")],
        [InlineKeyboardButton("\u274c Cancelar", callback_data="yt_cancel")],
    ]
    txt = "\U0001f4f9 *" + title + "*\n\u23f1 " + str(mins) + " min\n\nSelecciona el formato:"
    await status.edit_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT


async def handle_tiktok(update, context, url):
    status = await update.message.reply_text("\u23f3 Descargando TikTok sin marca de agua...")
    path = download_tiktok_no_watermark(url)
    if not path:
        await status.edit_text("\u274c No pude descargar ese TikTok.\nPuede ser privado, eliminado o la URL es invalida.")
        return ConversationHandler.END
    if os.path.getsize(path) > MAX_FILE_SIZE:
        cleanup(path)
        await status.edit_text("\u274c El video es demasiado grande para Telegram (max 300MB).")
        return ConversationHandler.END
    try:
        await status.edit_text("\U0001f4e4 Enviando video...")
        with open(path, "rb") as f:
            await update.message.reply_video(f, caption="\u2705 Descargado sin marca de agua", supports_streaming=True)
        await status.delete()
    except:
        await status.edit_text("\u274c Error al enviar. Intenta de nuevo.")
    finally:
        cleanup(path)
    return ConversationHandler.END


async def format_callback(update, context):
    q = update.callback_query
    await q.answer()
    choice = q.data
    url = context.user_data.get("youtube_url")
    if choice == "yt_cancel":
        await q.edit_message_text("\u2705 Cancelado.")
        return ConversationHandler.END
    if not url:
        await q.edit_message_text("\u274c Error: URL no encontrada.")
        return ConversationHandler.END
    await q.edit_message_text("\u23f3 Descargando...")
    fmt = {"yt_best": "best", "yt_medium": "best[height<=720]"}
    path = download_audio(url) if choice == "yt_audio" else download_video(url, fmt.get(choice, "best"))
    if not path:
        await q.edit_message_text("\u274c Error. Video grande? Prueba con audio.")
        return ConversationHandler.END
    if os.path.getsize(path) > MAX_FILE_SIZE:
        cleanup(path)
        await q.edit_message_text("\u274c Excede 300MB. Prueba con audio o menor calidad.")
        return ConversationHandler.END
    try:
        await q.edit_message_text("\U0001f4e4 Enviando...")
        if choice == "yt_audio":
            with open(path, "rb") as f: await q.message.reply_audio(f, caption="\u2705 Audio de YouTube")
        else:
            with open(path, "rb") as f: await q.message.reply_video(f, caption="\u2705 Video de YouTube", supports_streaming=True)
        await q.delete_message()
    except Exception:
        await q.edit_message_text("\u274c Error al enviar.")
    finally:
        cleanup(path)
    return ConversationHandler.END


async def cancel(update, context):
    await update.message.reply_text("\u2705 Operacion cancelada.")
    return ConversationHandler.END
