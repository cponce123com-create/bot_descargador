"""Async handlers para descarga."""

import os, re, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_FILE_SIZE
from services.file_utils import cleanup, cleanup_old_files

SELECTING_FORMAT = 1
YT_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE)
TT_RE = re.compile(r"(https?://)?(www\.)?(vm\.tiktok\.com|tiktok\.com)/", re.IGNORECASE)


def _err(e):
    m = {"ENV_ERROR":"Error temporal del servidor.","YOUTUBE_BLOCK":"YouTube bloquea. Usa /cookies.","VIDEO_PRIVADO":"Video privado.","VIDEO_NO_DISPONIBLE":"Video no disponible.","FORMATO_NO_DISPONIBLE":"Formato no disponible.","ARCHIVO_MUY_GRANDE":"Excede 300MB.","TIMEOUT":"Tardo mucho. Intenta audio."}
    for k,v in m.items():
        if k in e: return "❌ " + v
    return "❌ Error: " + e[:100]


def detect_platform(url):
    if YT_RE.search(url): return "youtube"
    if TT_RE.search(url): return "tiktok"
    return None


async def handle_message(up, ctx):
    t = up.message.text.strip(); p = detect_platform(t)
    if not p: await up.message.reply_text("❌ URL no valida."); return ConversationHandler.END
    cleanup_old_files()
    if p == "youtube": return await handle_youtube(up, ctx, t)
    return await handle_tiktok(up, ctx, t)


async def handle_youtube(up, ctx, url):
    from services.youtube import get_video_info
    s = await up.message.reply_text("⏳ Analizando...")
    info = get_video_info(url)
    if not info: await s.edit_text("❌ No pude obtener info."); return ConversationHandler.END
    ctx.user_data["yt_url"] = url
    t = info["title"][:50]+"..." if len(info["title"])>50 else info["title"]
    kb = [[InlineKeyboardButton("🎬 Mejor",callback_data="yt_best"),InlineKeyboardButton("📱 Mediano",callback_data="yt_medium")],
         [InlineKeyboardButton("🎵 Audio",callback_data="yt_audio")],
         [InlineKeyboardButton("❌ Cancelar",callback_data="yt_cancel")]]
    await s.edit_text("📹 *"+t+"*"+chr(10)+"Selecciona:",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT


async def handle_tiktok(up, ctx, url):
    from services.tiktok import download_tiktok_no_watermark
    s = await up.message.reply_text("⏳ TikTok...")
    path, direct_url, error = await asyncio.to_thread(download_tiktok_no_watermark, url)
    # Intentar envio directo por URL primero (Telegram descarga de CDN)
    if direct_url:
        try:
            await s.edit_text("📤 Enviando...")
            await up.message.reply_video(direct_url, caption="✅ Sin marca de agua (directo)", supports_streaming=True)
            await s.delete(); cleanup(path) if path else None; return ConversationHandler.END
        except Exception:
            logger = __import__("logging").getLogger(__name__)
            logger.info("TikTok direct URL failed, using local file")
    if not path:
        await s.edit_text("❌ No pude descargar."); return ConversationHandler.END
    if os.path.getsize(path) > MAX_FILE_SIZE: cleanup(path); await s.edit_text("❌ >300MB."); return ConversationHandler.END
    try:
        await s.edit_text("📤 Enviando...")
        with open(path,"rb") as f: await up.message.reply_video(f,caption="✅ Sin marca de agua",supports_streaming=True)
        await s.delete()
    except: await s.edit_text("❌ Error.")
    finally: cleanup(path)
    return ConversationHandler.END


async def format_callback(up, ctx):
    from services.youtube import download_video, download_audio
    q = up.callback_query; await q.answer()
    c = q.data; url = ctx.user_data.get("yt_url")
    if c == "yt_cancel": await q.edit_message_text("✅ Cancelado."); return ConversationHandler.END
    if not url: await q.edit_message_text("❌ URL perdida."); return ConversationHandler.END
    await q.edit_message_text("⏳ Descargando...")
    fm = {"yt_best":"best","yt_medium":"best[height<=720]"}
    # Non-blocking: ejecutar en thread pool
    if c == "yt_audio":
        path, err = await asyncio.to_thread(download_audio, url)
    else:
        path, err = await asyncio.to_thread(download_video, url, fm.get(c,"best"))
    if not path: await q.edit_message_text(_err(err)); return ConversationHandler.END
    if os.path.getsize(path) > MAX_FILE_SIZE: cleanup(path); await q.edit_message_text("❌ >300MB."); return ConversationHandler.END
    try:
        await q.edit_message_text("📤 Enviando...")
        if c=="yt_audio":
            with open(path,"rb") as f: await q.message.reply_audio(f,caption="✅ Audio")
        else:
            with open(path,"rb") as f: await q.message.reply_video(f,caption="✅ Video",supports_streaming=True)
        await q.delete_message()
    except: await q.edit_message_text("❌ Error.")
    finally: cleanup(path)
    return ConversationHandler.END


async def cancel(up, ctx):
    await up.message.reply_text("✅ Cancelado."); return ConversationHandler.END