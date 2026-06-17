"""Async handlers para descarga."""

import os, re, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_FILE_SIZE
from services.file_utils import cleanup, cleanup_old_files
SELECTING_FORMAT = 1
YT_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE)
TT_RE = re.compile(r"(https?://)?(www\.)?(vm\.tiktok\.com|tiktok\.com)/", re.IGNORECASE)

QUAL = {"yt_best":"Variable","yt_480":"480p","yt_audio":"Audio"}

def _err(e):
    m = {"ENV_ERROR":"Error temporal.","YOUTUBE_BLOCK":"Bloqueado. Usa /cookies.","VIDEO_PRIVADO":"Privado.","VIDEO_NO_DISPONIBLE":"No disponible.","FORMATO_NO_DISPONIBLE":"No disponible.","ARCHIVO_MUY_GRANDE":"Excede 300MB.","TIMEOUT":"Tardo mucho. Intenta otra calidad."}
    for k,v in m.items():
        if k in e: return "❌ " + v
    return "❌ " + e[:100]

def _caption(url, title, quality, platform):
    emoji = "✨📺 YouTube" if platform=="youtube" else "✨📺 TikTok"
    bar = "━"*25
    q = quality or "N/A"
    t = (title[:80]+"...") if title and len(title)>80 else (title or "Video")
    return f"{emoji}{chr(10)}{bar}{chr(10)}🔗 {url}{chr(10)}📝 {t}{chr(10)}📺 {q}{chr(10)}📥 Siap disimpan!"

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
    ctx.user_data["yt_title"] = info["title"]
    t = info["title"][:50]+"..." if len(info["title"])>50 else info["title"]
    kb = [[InlineKeyboardButton("🎬 Mejor",callback_data="yt_best"),InlineKeyboardButton("📱 480p",callback_data="yt_480")],
          [InlineKeyboardButton("🎵 Audio",callback_data="yt_audio"),InlineKeyboardButton("❌ Cancelar",callback_data="yt_cancel")]]
    await s.edit_text("📹 *"+t+"*"+chr(10)+"Selecciona:",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT

async def handle_tiktok(up, ctx, url):
    from services.tiktok import download_tiktok_no_watermark
    s = await up.message.reply_text("⏳ TikTok...")
    path, durl, err = await asyncio.to_thread(download_tiktok_no_watermark, url)
    if durl:
        try:
            await s.edit_text("📤 Enviando...");
            await up.message.reply_video(durl,caption=_caption(url,"TikTok","HD","tiktok"),supports_streaming=True);
            await s.delete(); cleanup(path) if path else None; return ConversationHandler.END
        except: pass
    if not path: await s.edit_text("❌ No pude descargar."); return ConversationHandler.END
    if os.path.getsize(path)>MAX_FILE_SIZE: cleanup(path); await s.edit_text("❌ >300MB."); return ConversationHandler.END
    try:
        await s.edit_text("📤 Enviando...");
        with open(path,"rb") as f: await up.message.reply_video(f,caption=_caption(url,"TikTok","HD","tiktok"),supports_streaming=True);
        await s.delete()
    except: await s.edit_text("❌ Error.")
    finally: cleanup(path)
    return ConversationHandler.END

async def format_callback(up, ctx):
    from services.youtube import download_video, download_audio
    q = up.callback_query; await q.answer()
    c = q.data; url = ctx.user_data.get("yt_url"); title = ctx.user_data.get("yt_title","")
    if c=="yt_cancel": await q.edit_message_text("✅ Cancelado."); return ConversationHandler.END
    if not url: await q.edit_message_text("❌ URL perdida."); return ConversationHandler.END
    await q.edit_message_text("⏳ Descargando...")
    fm = {"yt_best":"best","yt_480":"best[height<=480]"}
    if c=="yt_audio":
        path, err = await asyncio.to_thread(download_audio, url)
    else:
        path, err = await asyncio.to_thread(download_video, url, fm.get(c,"best"))
    if not path: await q.edit_message_text(_err(err)); return ConversationHandler.END
    if os.path.getsize(path)>MAX_FILE_SIZE: cleanup(path); await q.edit_message_text("❌ >300MB."); return ConversationHandler.END
    quality = QUAL.get(c,"N/A")
    try:
        await q.edit_message_text("📤 Enviando...")
        if c=="yt_audio":
            with open(path,"rb") as f: await q.message.reply_audio(f,caption=_caption(url,title,quality,"youtube"))
        else:
            with open(path,"rb") as f: await q.message.reply_video(f,caption=_caption(url,title,quality,"youtube"),supports_streaming=True)
        await q.delete_message()
    except: await q.edit_message_text("❌ Error.")
    finally: cleanup(path)
    return ConversationHandler.END

async def cancel(up, ctx):
    await up.message.reply_text("✅ Cancelado."); return ConversationHandler.END