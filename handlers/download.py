"""Async handlers."""

import os, re, asyncio, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_FILE_SIZE, ALLOWED_USER_IDS
from services.file_utils import cleanup, cleanup_old_files

logger = logging.getLogger(__name__)
SELECTING_FORMAT = 1
NL = chr(10)


async def _require_auth(up: Update) -> bool:
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

QUAL = {"video": "360p", "vertical": "Vertical 9:16", "audio": "MP3"}


def _escape_md(text):
    if not text:
        return text
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, "\\" + ch)
    return text


def _err(e):
    m = {"ENV_ERROR": "Error del servidor.", "YOUTUBE_BLOCK": "Bloqueado. Usa /cookies.",
         "TIMEOUT": "Tardo mucho. Reintenta.", "FORMATO_NO_DISPONIBLE": "No disponible.",
         "ARCHIVO_MUY_GRANDE": "Excede 300MB."}
    for k, v in m.items():
        if k in e:
            return "❌ " + v
    return "❌ " + e[:100]


def _cap(url, title, quality, plat):
    emojis = {"youtube": "✨📺 YouTube", "tiktok": "✨📺 TikTok", "facebook": "✨📺 Facebook",
              "instagram": "✨📸 Instagram", "x": "✨🐦 X", "reddit": "✨🤖 Reddit",
              "pinterest": "✨📌 Pinterest"}
    e = emojis.get(plat, "✨📺 Video")
    t = _escape_md(title[:80] + "...") if title and len(title) > 80 else _escape_md(title or "Video")
    sep = "━" * 25
    return NL.join([e, sep, "🔗 " + url, "📝 " + t, "📺 " + quality, "📥 ¡Guardado!"])


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
    if not query:
        await up.message.reply_text("❌ Uso: /search [termino]")
        return
    s = await up.message.reply_text("🔍 Buscando '" + query + "'...")
    from services.youtube import _run
    ok, o, serr = _run(["ytsearch5:" + query, "--get-title", "--get-id", "--flat-playlist"],
                       30, use_ejs=False)
    if not ok or not o:
        await s.edit_text("❌ Sin resultados.")
        return
    lines = o.split(NL)
    kb = []
    for i in range(0, len(lines), 2):
        if i + 1 < len(lines):
            kb.append([InlineKeyboardButton("🎬 " + lines[i][:40],
                                            callback_data="yt_search_" + lines[i + 1])])
    await s.edit_text("🎯 Resultados:", reply_markup=InlineKeyboardMarkup(kb))


from telegram.constants import ChatAction


def _extract_url(text):
    for pattern in (YT_RE, TT_RE, FB_RE, IG_RE, X_RE, REDDIT_RE, PINTEREST_RE):
        m = pattern.search(text)
        if m:
            start = m.start()
            url_start = text.rfind("https://", 0, start)
            if url_start == -1:
                url_start = text.rfind("http://", 0, start)
            if url_start == -1:
                url_start = start
            end = start
            while end < len(text) and text[end] not in (" ", NL, "\t"):
                end += 1
            return text[url_start:end].strip()
    return None


async def _react(msg, emoji):
    try:
        await msg.set_reaction(emoji)
    except Exception:
        pass


async def handle_message(up, ctx):
    from handlers.verify import require_channel, verify_prompt
    if not await require_channel(up, ctx):
        await verify_prompt(up, ctx)
        return ConversationHandler.END
    if not await _require_auth(up): return ConversationHandler.END
    if not up.message:
        return ConversationHandler.END
    t = up.message.text or up.message.caption or ""
    if not t.strip():
        await up.message.reply_text("❌ URL no valida.")
        return ConversationHandler.END
    url = _extract_url(t)
    if not url:
        await up.message.reply_text("❌ URL no valida.")
        return ConversationHandler.END
    p = detect_platform(url)
    if not p:
        await up.message.reply_text("❌ URL no valida.")
        return ConversationHandler.END
    trim_match = re.search(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", t)
    if trim_match:
        ctx.user_data["trim"] = trim_match.groups()
    await asyncio.to_thread(cleanup_old_files)
    if p == "youtube": return await handle_youtube(up, ctx, url)
    if p == "tiktok": return await handle_tiktok(up, ctx, url)
    if p == "facebook": return await handle_facebook(up, ctx, url)
    if p == "instagram": return await handle_instagram(up, ctx, url)
    return await handle_generic(up, ctx, url, p)


async def handle_youtube(up, ctx, url):
    from services.youtube import get_video_info, _get_yt_thumbnail
    await _react(up.message, "👀")
    s = await up.message.reply_text("⏳ Analizando...")
    info = await asyncio.to_thread(get_video_info, url)
    thumb = _get_yt_thumbnail(url)
    ctx.user_data["yt_url"] = url
    ctx.user_data["yt_title"] = info["title"]
    kb = [[InlineKeyboardButton("🎬 Video", callback_data="yt_video"),
            InlineKeyboardButton("📱 Vertical", callback_data="yt_vertical")],
           [InlineKeyboardButton("🎵 Audio", callback_data="yt_audio")]]
    if YT_PL_RE.search(url):
        kb.append([InlineKeyboardButton("🎼 Playlist (Top 10)", callback_data="yt_playlist")])
    kb.append([InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")])
    safe_title = _escape_md(info["title"][:50] + "...") if len(info["title"]) > 50 else _escape_md(info["title"])
    await _react(up.message, "📹")
    caption = "📹 *" + safe_title + "*" + NL + "Selecciona:"
    if thumb:
        await up.message.reply_photo(thumb, caption=caption, parse_mode="Markdown",
                                     reply_markup=InlineKeyboardMarkup(kb))
        await s.delete()
    else:
        await s.edit_text(caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT


async def handle_tiktok(up, ctx, url):
    from services.tiktok import download_tiktok_no_watermark
    await _react(up.message, "🫡")
    await ctx.bot.send_chat_action(up.effective_chat.id, ChatAction.RECORD_VIDEO)
    s = await up.message.reply_text("⏳ TikTok...")
    path, durl, err = await asyncio.to_thread(download_tiktok_no_watermark, url)
    if durl:
        try:
            await ctx.bot.send_chat_action(up.effective_chat.id, ChatAction.UPLOAD_VIDEO)
            await up.message.reply_video(durl, caption=_cap(url, "TikTok", "HD", "tiktok"),
                                         supports_streaming=True)
            await s.delete()
            if path:
                cleanup(path)
            return ConversationHandler.END
        except Exception:
            logger.debug("TikTok direct URL send failed, falling back to file")
    if path:
        await ctx.bot.send_chat_action(up.effective_chat.id, ChatAction.UPLOAD_VIDEO)
        with open(path, "rb") as f:
            await up.message.reply_video(f, caption=_cap(url, "TikTok", "HD", "tiktok"),
                                         supports_streaming=True)
        await s.delete()
        cleanup(path)
        return ConversationHandler.END
    await s.edit_text("❌ Error.")
    return ConversationHandler.END


async def _send_or_fallback(bot, chat_id, path, title, url, quality, plat, is_audio=False):
    sz = os.path.getsize(path)
    TELEGRAM_LIMIT = 50 * 1024 * 1024
    if sz > TELEGRAM_LIMIT:
        from services.filebin import upload
        file_url = upload(path)
        if file_url:
            msg = ("📥 *" + title + "* es muy grande (" + str(sz // 1024 // 1024) +
                   "MB) para Telegram." + NL + "Descarga aqui: " + file_url)
            return await bot.send_message(chat_id, msg, disable_web_page_preview=True)
    if is_audio:
        with open(path, "rb") as f:
            return await bot.send_audio(chat_id, f, caption=_cap(url, title, quality, plat),
                                        write_timeout=120)
    else:
        with open(path, "rb") as f:
            return await bot.send_video(chat_id, f, caption=_cap(url, title, quality, plat),
                                        supports_streaming=True, write_timeout=120)


async def format_callback(up, ctx):
    q = up.callback_query
    c = q.data
    await q.answer()
    path = None
    meta = {}

    try:
        from services.youtube import download_video, download_audio
        if c.startswith("yt_search_"):
            vid = c.replace("yt_search_", "")
            url = "https://www.youtube.com/watch?v=" + vid
            await q.message.delete()
            return await handle_youtube(up, ctx, url)

        url = ctx.user_data.get("yt_url")
        title = ctx.user_data.get("yt_title", "")

        if c == "yt_cancel":
            await q.message.reply_text("✅ Cancelado.")
            return ConversationHandler.END

        await _react(q.message, "🫡")
        await ctx.bot.send_chat_action(q.message.chat_id, ChatAction.RECORD_VIDEO)

        loop = asyncio.get_running_loop()

        def progress(p):
            try:
                bar = chr(9608) * int(p // 10) + chr(9617) * (10 - int(p // 10))
                if int(p) % 20 == 0:
                    asyncio.run_coroutine_threadsafe(
                        q.message.reply_text(bar + " " + "{:.0f}".format(p) + "%"), loop)
            except Exception as e:
                logger.warning("progress callback failed: %s", e)

        trim = ctx.user_data.get("trim")
        sem = ctx.bot_data.get("download_sem")
        if sem:
            await sem.acquire()
        try:
            if c == "yt_playlist":
                from services.youtube import download_playlist_audio
                paths, err = await asyncio.to_thread(download_playlist_audio, url)
                if paths:
                    for p in paths:
                        with open(p, "rb") as f:
                            await q.message.reply_audio(f)
                        cleanup(p)
                    return ConversationHandler.END
            elif c == "yt_audio":
                path, err = await asyncio.to_thread(download_audio, url, progress)
            else:
                fmt = "720" if c == "yt_vertical" else "360"
                path, err, meta = await asyncio.to_thread(
                    download_video, url, fmt, progress,
                    trim[0] if trim else None, trim[1] if trim else None)
        finally:
            if sem:
                sem.release()

        if path:
            await _react(q.message, "🚀")
            await ctx.bot.send_chat_action(q.message.chat_id, ChatAction.UPLOAD_VIDEO)
            quality = meta.get("resolution", QUAL.get(c, "HD"))
            await _send_or_fallback(ctx.bot, q.message.chat_id, path, title, url, quality, "youtube",
                                    is_audio=(c == "yt_audio"))
            cleanup(path)
            path = None
        else:
            await q.message.reply_text(_err(err))
    except Exception as e:
        logger.exception("Error en format_callback")
        try:
            await q.message.reply_text("❌ Error. Reintenta.")
        except Exception:
            pass
    finally:
        if path:
            cleanup(path)
    return ConversationHandler.END


async def handle_facebook(up, ctx, url):
    ctx.user_data["gen_url"] = url
    ctx.user_data["gen_title"] = "Facebook Video"
    return await handle_generic(up, ctx, url, "facebook")


async def handle_instagram(up, ctx, url):
    ctx.user_data["gen_url"] = url
    ctx.user_data["gen_title"] = "Instagram Post"
    return await handle_generic(up, ctx, url, "instagram")


async def handle_generic(up, ctx, url, plat):
    from services.generic import get_info
    s = await up.message.reply_text("⏳ Analizando " + plat + "...")
    info = await asyncio.to_thread(get_info, url)
    ctx.user_data["gen_url"] = url
    ctx.user_data["gen_title"] = info["title"]
    kb = [[InlineKeyboardButton("🎬 Video", callback_data="gen_video_" + plat),
            InlineKeyboardButton("🎵 Audio", callback_data="gen_audio_" + plat)],
           [InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    safe_title = _escape_md(info["title"][:50] + "...") if len(info["title"]) > 50 else _escape_md(info["title"])
    caption = "📹 *" + safe_title + "*" + NL + "Selecciona:"
    if info.get("thumbnail"):
        await up.message.reply_photo(info["thumbnail"], caption=caption, parse_mode="Markdown",
                                     reply_markup=InlineKeyboardMarkup(kb))
        await s.delete()
    else:
        await s.edit_text(caption, reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT


async def handle_generic_download(up, ctx):
    try:
        from services.generic import download_generic
        from services.youtube import download_video, download_audio
        q = up.callback_query
        await q.answer()
        c = q.data
        url = ctx.user_data.get("gen_url")
        title = ctx.user_data.get("gen_title", "Video")
        plat = c.split("_")[-1]
        status = await q.message.reply_text("⏳ Descargando...")

        loop = asyncio.get_running_loop()

        def progress(p):
            try:
                asyncio.run_coroutine_threadsafe(
                    status.edit_text("⏳ " + "{:.0f}".format(p) + "%"), loop)
            except Exception as e:
                logger.warning("progress callback failed: %s", e)

        trim = ctx.user_data.get("trim")
        sem = ctx.bot_data.get("download_sem")
        if sem:
            await sem.acquire()
        try:
            if "_audio_" in c:
                path, err = await asyncio.to_thread(download_audio, url, progress)
            else:
                path, err = await asyncio.to_thread(download_generic, url, plat, progress)
        finally:
            if sem:
                sem.release()

        if path:
            sz = os.path.getsize(path)
            if sz > MAX_FILE_SIZE:
                cleanup(path)
                await status.edit_text("❌ Excede " + str(MAX_FILE_SIZE // 1024 // 1024) + "MB.")
                return ConversationHandler.END
            with open(path, "rb") as f:
                if "_audio_" in c:
                    await status.reply_audio(f, caption=_cap(url, title, "MP3", plat))
                else:
                    await status.reply_video(f, caption=_cap(url, title, "HD", plat),
                                             supports_streaming=True)
            cleanup(path)
        else:
            await status.edit_text(_err(err))
        return ConversationHandler.END
    except Exception as e:
        logger.error("Error en handle_generic_download: %s", e)
        return ConversationHandler.END


async def cancel(up, ctx):
    await up.message.reply_text("✅ Cancelado.")
    return ConversationHandler.END
