"""Async handlers."""

import os, re, asyncio, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_FILE_SIZE, ALLOWED_USER_IDS
from services.file_utils import cleanup, cleanup_old_files

logger = logging.getLogger(__name__)
SELECTING_FORMAT = 1


async def _require_auth(up: Update) -> bool:
    """Check if user is authorized. Returns False if blocked."""
    if ALLOWED_USER_IDS is None:
        return True
    uid = up.effective_user.id if up.effective_user else None
    if uid and uid in ALLOWED_USER_IDS:
        return True
    logger.info("Blocked uid=%s", uid)
    return False

YT_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE)
YT_PL_RE = re.compile(r"list=([a-zA-Z0-9_-]+)", re.IGNORECASE)
TT_RE = re.compile(r"(https?://)?(www\.)?(vm\.tiktok\.com|tiktok\.com)/", re.IGNORECASE)
FB_RE = re.compile(r"(https?://)?(www\.|web\.|m\.)?(facebook\.com|fb\.watch)/", re.IGNORECASE)
IG_RE = re.compile(r"(https?://)?(www\.)?(instagram\.com)/(p|reels|reel|tv)/", re.IGNORECASE)
X_RE = re.compile(r"(https?://)?(www\.|x\.|twitter\.)?(com)/(.*)/status/", re.IGNORECASE)
REDDIT_RE = re.compile(r"(https?://)?(www\.)?(reddit\.com|v\.redd\.it)/", re.IGNORECASE)
PINTEREST_RE = re.compile(r"(https?://)?(www\.|id\.|pin\.)?(pinterest\.com|pin\.it)/", re.IGNORECASE)

QUAL = {"video":"360p","vertical":"Vertical 9:16","audio":"MP3", "gif": "GIF"}

def _escape_md(text):
    """Escape MarkdownV1 special characters so user-provided text
    (titles with _, *, [, ], etc.) doesn't break parse_mode formatting."""
    if not text:
        return text
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, "\\" + ch)
    return text

def _err(e):
    m = {"ENV_ERROR":"Error del servidor.","YOUTUBE_BLOCK":"Bloqueado. Usa /cookies.","TIMEOUT":"Tardo mucho. Reintenta.","FORMATO_NO_DISPONIBLE":"No disponible.","ARCHIVO_MUY_GRANDE":"Excede 300MB."}
    for k,v in m.items():
        if k in e: return "❌ "+v
    return "❌ "+e[:100]

def _cap(url,title,quality,plat):
    m = {"youtube":"✨📺 YouTube","tiktok":"✨📺 TikTok","facebook":"✨📺 Facebook","instagram":"✨📸 Instagram","x":"✨🐦 X","reddit":"✨🤖 Reddit","pinterest":"✨📌 Pinterest"}
    e = m.get(plat, "✨📺 Video")
    t = _escape_md(title[:80] + "...") if title and len(title)>80 else _escape_md(title or "Video")
    return f"{e}\n━"*10 + f"\n🔗 {url}\n📝 {t}\n📺 {quality}\n📥 ¡Guardado!"

def detect_platform(url):
    if YT_RE.search(url): return "youtube"
    if TT_RE.search(url): return "tiktok"
    if FB_RE.search(url): return "facebook"
    if IG_RE.search(url): return "instagram"
    if X_RE.search(url): return "x"
    if REDDIT_RE.search(url): return "reddit"
    if PINTEREST_RE.search(url): return "pinterest"
    return None

async def handle_search(up, ctx):
    if not await _require_auth(up): return
    query = " ".join(ctx.args)
    if not query: await up.message.reply_text("❌ Uso: /search [termino]"); return
    s = await up.message.reply_text(f"🔍 Buscando '{query}'...")
    from services.youtube import _run
    ok, o, serr = _run([f"ytsearch5:{query}", "--get-title", "--get-id", "--flat-playlist"], 30)
    if not ok or not o: await s.edit_text("❌ Sin resultados."); return
    lines = o.split('\n'); kb = []
    for i in range(0, len(lines), 2):
        if i+1 < len(lines): kb.append([InlineKeyboardButton(f"🎬 {lines[i][:40]}", callback_data=f"yt_search_{lines[i+1]}")])
    await s.edit_text("🎯 Resultados:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_message(up, ctx):
    if not await _require_auth(up): return ConversationHandler.END
    t = up.message.text.strip(); p = detect_platform(t)
    trim_match = re.search(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", t)
    if trim_match:
        ctx.user_data["trim"] = trim_match.groups()
        t = t.replace(trim_match.group(0), "").strip(); p = detect_platform(t)
    if not p: await up.message.reply_text("❌ URL no valida."); return ConversationHandler.END
    cleanup_old_files()
    if p=="youtube": return await handle_youtube(up,ctx,t)
    if p=="tiktok": return await handle_tiktok(up,ctx,t)
    if p=="facebook": return await handle_facebook(up,ctx,t)
    if p=="instagram": return await handle_instagram(up,ctx,t)
    return await handle_generic(up,ctx,t,p)

async def handle_youtube(up, ctx, url):
    from services.youtube import get_video_info
    from services.generic import get_info as get_generic_info
    s = await up.message.reply_text("⏳ Analizando...")
    info = await asyncio.to_thread(get_video_info, url)
    gen_info = await asyncio.to_thread(get_generic_info, url)
    thumb = gen_info.get("thumbnail")
    ctx.user_data["yt_url"]=url; ctx.user_data["yt_title"]=info["title"]
    kb = [[InlineKeyboardButton("🎬 Video",callback_data="yt_video"),InlineKeyboardButton("📱 Vertical",callback_data="yt_vertical")],
          [InlineKeyboardButton("🎵 Audio",callback_data="yt_audio"), InlineKeyboardButton("🎞 GIF", callback_data="yt_gif")]]
    if YT_PL_RE.search(url): kb.append([InlineKeyboardButton("🎼 Playlist (Top 10)", callback_data="yt_playlist")])
    kb.append([InlineKeyboardButton("❌ Cancelar",callback_data="yt_cancel")])
    safe_title = _escape_md(info["title"][:50] + "...") if len(info["title"]) > 50 else _escape_md(info["title"])
    if thumb:
        await up.message.reply_photo(thumb, caption=f"📹 *{safe_title}*\nSelecciona:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        await s.delete()
    else:
        await s.edit_text(f"📹 *{safe_title}*\nSelecciona:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT

async def handle_tiktok(up, ctx, url):
    from services.tiktok import download_tiktok_no_watermark
    s = await up.message.reply_text("⏳ TikTok...")
    path,durl,err = await asyncio.to_thread(download_tiktok_no_watermark,url)
    if durl:
        try:
            await up.message.reply_video(durl,caption=_cap(url,"TikTok","HD","tiktok"),supports_streaming=True)
            await s.delete(); cleanup(path) if path else None; return ConversationHandler.END
        except: pass
    if path:
        with open(path,"rb") as f: await up.message.reply_video(f,caption=_cap(url,"TikTok","HD","tiktok"),supports_streaming=True)
        await s.delete(); cleanup(path); return ConversationHandler.END
    await s.edit_text("❌ Error."); return ConversationHandler.END

async def format_callback(up, ctx):
    q = up.callback_query
    c = q.data
    await q.answer()
    path = None
    status_msg = None  # track status message for deletion later

    try:
        from services.youtube import download_video, download_audio
        if c.startswith("yt_search_"):
            url = f"https://www.youtube.com/watch?v={c.replace('yt_search_', '')}"
            await q.message.delete(); return await handle_youtube(up, ctx, url)
    
        url = ctx.user_data.get("yt_url"); title = ctx.user_data.get("yt_title","")
        
        if c=="yt_cancel":
            await q.message.reply_text("✅ Cancelado.")
            return ConversationHandler.END

        # Send a NEW status message instead of editing the photo/buttons message
        status_msg = await q.message.reply_text("⏳ Descargando...")
        
        def progress(p):
            try:
                bar = "█" * int(p//10) + "░" * (10 - int(p//10))
                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(status_msg.edit_text(f"⏳ {bar} {p:.0f}%"), loop)
            except: pass

        trim = ctx.user_data.get("trim")
        sem = ctx.bot_data.get("download_sem")
        if sem:
            await sem.acquire()
        try:
            if c=="yt_playlist":
                from services.youtube import download_playlist_audio
                paths, err = await asyncio.to_thread(download_playlist_audio, url)
                if paths:
                    for p in paths:
                        with open(p, "rb") as f: await q.message.reply_audio(f)
                        cleanup(p)
                    return ConversationHandler.END
            elif c=="yt_audio": path, err = await asyncio.to_thread(download_audio, url, progress)
            elif c=="yt_gif": path, err = await asyncio.to_thread(download_video, url, progress_callback=progress, to_gif=True, start_time=trim[0] if trim else None, end_time=trim[1] if trim else None)
            else: path, err = await asyncio.to_thread(download_video, url, format_id=("vertical" if c=="yt_vertical" else "360"), progress_callback=progress, start_time=trim[0] if trim else None, end_time=trim[1] if trim else None)
        finally:
            if sem:
                sem.release()
        
        if path:
            with open(path,"rb") as f:
                if c=="yt_audio": await status_msg.reply_audio(f, caption=_cap(url,title,"MP3","youtube"))
                elif c=="yt_gif": await status_msg.reply_animation(f, caption=_cap(url,title,"GIF","youtube"))
                else: await status_msg.reply_video(f, caption=_cap(url,title,QUAL.get(c,"HD"),"youtube"), supports_streaming=True)
            cleanup(path); path = None
        else:
            await status_msg.edit_text(_err(err))
    except Exception as e:
        logger.exception("Error en format_callback")
        try:
            if status_msg:
                await status_msg.edit_text("❌ Error. Reintenta.")
            else:
                await q.message.reply_text("❌ Error. Reintenta.")
        except Exception:
            pass
    finally:
        if path: cleanup(path)
    return ConversationHandler.END

async def handle_facebook(up, ctx, url):
    ctx.user_data["gen_url"] = url; ctx.user_data["gen_title"] = "Facebook Video"
    return await handle_generic(up, ctx, url, "facebook")

async def handle_instagram(up, ctx, url):
    ctx.user_data["gen_url"] = url; ctx.user_data["gen_title"] = "Instagram Post"
    return await handle_generic(up, ctx, url, "instagram")

async def handle_generic(up, ctx, url, plat):
    from services.generic import get_info
    s = await up.message.reply_text(f"⏳ Analizando {plat}...")
    info = await asyncio.to_thread(get_info, url)
    ctx.user_data["gen_url"] = url; ctx.user_data["gen_title"] = info["title"]
    kb = [[InlineKeyboardButton("🎬 Video", callback_data=f"gen_video_{plat}"), InlineKeyboardButton("🎵 Audio", callback_data=f"gen_audio_{plat}")],
          [InlineKeyboardButton("🎞 GIF", callback_data=f"gen_gif_{plat}"), InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    safe_title = _escape_md(info["title"][:50] + "...") if len(info["title"]) > 50 else _escape_md(info["title"])
    if info.get("thumbnail"):
        await up.message.reply_photo(info["thumbnail"], caption=f"📹 *{safe_title}*\nSelecciona:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        await s.delete()
    else: await s.edit_text(f"📹 *{safe_title}*\nSelecciona:", reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT

async def handle_generic_download(up, ctx):
    try:
        from services.generic import download_generic
        from services.youtube import download_video, download_audio
        q = up.callback_query; await q.answer(); c = q.data
        url = ctx.user_data.get("gen_url"); title = ctx.user_data.get("gen_title", "Video")
        plat = c.split("_")[-1]
        # Send new status message (photo-safe)
        status = await q.message.reply_text("⏳ Descargando...")
        def progress(p):
            try:
                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(status.edit_text(f"⏳ {p:.0f}%"), loop)
            except: pass

        trim = ctx.user_data.get("trim")
        # Acquire global semaphore to cap concurrent downloads
        sem = ctx.bot_data.get("download_sem")
        if sem:
            await sem.acquire()
        try:
            if "_audio_" in c: path, err = await asyncio.to_thread(download_audio, url, progress)
            elif "_gif_" in c: path, err = await asyncio.to_thread(download_video, url, to_gif=True, progress_callback=progress, start_time=trim[0] if trim else None, end_time=trim[1] if trim else None)
            else: path, err = await asyncio.to_thread(download_generic, url, plat, progress)
        finally:
            if sem:
                sem.release()

        if path:
            sz = os.path.getsize(path)
            if sz > MAX_FILE_SIZE:
                cleanup(path)
                await status.edit_text(f"❌ Excede {MAX_FILE_SIZE//1024//1024}MB.")
                return ConversationHandler.END
            with open(path, "rb") as f:
                if "_audio_" in c: await status.reply_audio(f, caption=_cap(url, title, "MP3", plat))
                elif "_gif_" in c: await status.reply_animation(f, caption=_cap(url, title, "GIF", plat))
                else: await status.reply_video(f, caption=_cap(url, title, "HD", plat), supports_streaming=True)
            cleanup(path)
        else:
            await status.edit_text(_err(err))
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error en handle_generic_download: {e}")
        return ConversationHandler.END

async def cancel(up, ctx):
    await up.message.reply_text("✅ Cancelado."); return ConversationHandler.END
