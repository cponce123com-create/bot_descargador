"""Async handlers."""

import os, re, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_FILE_SIZE
from services.file_utils import cleanup, cleanup_old_files
SELECTING_FORMAT = 1
YT_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE)
YT_PL_RE = re.compile(r"list=([a-zA-Z0-9_-]+)", re.IGNORECASE)
TT_RE = re.compile(r"(https?://)?(www\.)?(vm\.tiktok\.com|tiktok\.com)/", re.IGNORECASE)
FB_RE = re.compile(r"(https?://)?(www\.|web\.|m\.)?(facebook\.com|fb\.watch)/", re.IGNORECASE)
IG_RE = re.compile(r"(https?://)?(www\.)?(instagram\.com)/(p|reels|reel|tv)/", re.IGNORECASE)
QUAL = {"video":"360p","vertical":"Vertical 9:16","audio":"MP3"}

def _err(e):
    m = {"ENV_ERROR":"Error del servidor.","YOUTUBE_BLOCK":"Bloqueado. Usa /cookies.","TIMEOUT":"Tardo mucho. Reintenta.","FORMATO_NO_DISPONIBLE":"No disponible.","ARCHIVO_MUY_GRANDE":"Excede 300MB."}
    for k,v in m.items():
        if k in e: return "❌ "+v
    return "❌ "+e[:100]

def _cap(url,title,quality,plat):
    if plat=="youtube": e = "✨📺 YouTube"
    elif plat=="tiktok": e = "✨📺 TikTok"
    elif plat=="facebook": e = "✨📺 Facebook"
    else: e = "✨📸 Instagram"
    t = (title[:80]+"...") if title and len(title)>80 else (title or "Video")
    return f"{e}{chr(10)}"+"━"*25+f"{chr(10)}🔗 {url}{chr(10)}📝 {t}{chr(10)}📺 {quality}{chr(10)}📥 ¡Dale en guardar!"

def detect_platform(url):
    if YT_RE.search(url): return "youtube"
    if TT_RE.search(url): return "tiktok"
    if FB_RE.search(url): return "facebook"
    if IG_RE.search(url): return "instagram"
    return None

async def handle_message(up, ctx):
    t = up.message.text.strip(); p = detect_platform(t)
    if not p: await up.message.reply_text("❌ URL no valida."); return ConversationHandler.END
    cleanup_old_files()
    if p=="youtube": return await handle_youtube(up,ctx,t)
    if p=="tiktok": return await handle_tiktok(up,ctx,t)
    if p=="facebook": return await handle_facebook(up,ctx,t)
    return await handle_instagram(up,ctx,t)

async def handle_youtube(up, ctx, url):
    from services.youtube import get_video_info
    s = await up.message.reply_text("⏳ Analizando...")
    info = get_video_info(url)
    if not info: await s.edit_text("❌ No pude obtener info."); return ConversationHandler.END
    ctx.user_data["yt_url"]=url; ctx.user_data["yt_title"]=info["title"]
    t = info["title"][:50]+"..." if len(info["title"])>50 else info["title"]
    kb = [[InlineKeyboardButton("🎬 Video",callback_data="yt_video"),InlineKeyboardButton("📱 Vertical",callback_data="yt_vertical")],
          [InlineKeyboardButton("🎵 Audio",callback_data="yt_audio")]]
    
    if YT_PL_RE.search(url):
        kb.append([InlineKeyboardButton("🎼 Playlist (Top 10 MP3)", callback_data="yt_playlist")])
        
    kb.append([InlineKeyboardButton("❌ Cancelar",callback_data="yt_cancel")])
    await s.edit_text("📹 *"+t+"*"+chr(10)+"Selecciona:",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_FORMAT

async def handle_tiktok(up, ctx, url):
    from services.tiktok import download_tiktok_no_watermark
    s = await up.message.reply_text("⏳ TikTok...")
    path,durl,err = await asyncio.to_thread(download_tiktok_no_watermark,url)
    if durl:
        try:
            await s.edit_text("📤 Enviando...")
            await up.message.reply_video(durl,caption=_cap(url,"TikTok","HD","tiktok"),supports_streaming=True)
            await s.delete(); cleanup(path) if path else None; return ConversationHandler.END
        except: pass
    if not path: await s.edit_text("❌ No pude descargar."); return ConversationHandler.END
    if os.path.getsize(path)>MAX_FILE_SIZE: cleanup(path); await s.edit_text("❌ >300MB."); return ConversationHandler.END
    try:
        await s.edit_text("📤 Enviando...")
        with open(path,"rb") as f: await up.message.reply_video(f,caption=_cap(url,"TikTok","HD","tiktok"),supports_streaming=True)
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
    if c=="yt_playlist":
        from services.youtube import download_playlist_audio
        await q.edit_message_text("⏳ Descargando playlist (máx 10 canciones)...")
        paths, err = await asyncio.to_thread(download_playlist_audio, url)
        if not paths:
            await q.edit_message_text(_err(err))
            return ConversationHandler.END
        
        await q.edit_message_text(f"📤 Enviando {len(paths)} canciones...")
        for p in paths:
            try:
                with open(p, "rb") as f:
                    await q.message.reply_audio(f)
            except: pass
            finally:
                from services.file_utils import cleanup
                cleanup(p)
        await q.delete_message()
        return ConversationHandler.END

    if c=="yt_audio": path,err = await asyncio.to_thread(download_audio,url)
    else: path,err = await asyncio.to_thread(download_video,url,("vertical" if c=="yt_vertical" else "360"))
    if not path: await q.edit_message_text(_err(err)); return ConversationHandler.END
    if os.path.getsize(path)>MAX_FILE_SIZE: cleanup(path); await q.edit_message_text("❌ >300MB."); return ConversationHandler.END
    quality = QUAL.get(c,"360p")
    try:
        await q.edit_message_text("📤 Enviando...")
        if c=="yt_audio":
            with open(path,"rb") as f: await q.message.reply_audio(f,caption=_cap(url,title,quality,"youtube"))
        else:
            with open(path,"rb") as f: await q.message.reply_video(f,caption=_cap(url,title,quality,"youtube"),supports_streaming=True)
        await q.delete_message()
    except: await q.edit_message_text("❌ Error.")
    finally: cleanup(path)
    return ConversationHandler.END

async def handle_facebook(up, ctx, url):
    from services.facebook import get_video_info, download_facebook
    s = await up.message.reply_text("⏳ Analizando Facebook...")
    info = await asyncio.to_thread(get_video_info, url)
    title = info.get("title", "Facebook Video")
    
    await s.edit_text("⏳ Descargando video de Facebook...")
    path, err = await asyncio.to_thread(download_facebook, url)
    
    if not path:
        await s.edit_text(_err(err))
        return ConversationHandler.END
        
    if os.path.getsize(path) > MAX_FILE_SIZE:
        from services.file_utils import cleanup
        cleanup(path)
        await s.edit_text("❌ El archivo es demasiado grande (>300MB).")
        return ConversationHandler.END

    try:
        await s.edit_text("📤 Enviando...")
        with open(path, "rb") as f:
            await up.message.reply_video(
                f, 
                caption=_cap(url, title, "HD", "facebook"),
                supports_streaming=True
            )
        await s.delete()
    except Exception as e:
        await s.edit_text(f"❌ Error al enviar: {str(e)[:50]}")
    finally:
        from services.file_utils import cleanup
        cleanup(path)
    return ConversationHandler.END

async def handle_instagram(up, ctx, url):
    from services.instagram import get_instagram_info, download_instagram
    s = await up.message.reply_text("⏳ Analizando Instagram...")
    info = await asyncio.to_thread(get_instagram_info, url)
    title = info.get("title", "Instagram Post")
    
    await s.edit_text("⏳ Descargando contenido de Instagram...")
    path, err = await asyncio.to_thread(download_instagram, url)
    
    if not path:
        await s.edit_text(_err(err))
        return ConversationHandler.END
        
    if os.path.getsize(path) > MAX_FILE_SIZE:
        from services.file_utils import cleanup
        cleanup(path)
        await s.edit_text("❌ Archivo muy grande (>300MB).")
        return ConversationHandler.END

    try:
        await s.edit_text("📤 Enviando...")
        with open(path, "rb") as f:
            await up.message.reply_video(
                f, 
                caption=_cap(url, title, "HD", "instagram"),
                supports_streaming=True
            )
        await s.delete()
    except Exception as e:
        await s.edit_text(f"❌ Error al enviar: {str(e)[:50]}")
    finally:
        from services.file_utils import cleanup
        cleanup(path)
    return ConversationHandler.END

async def cancel(up, ctx):
    await up.message.reply_text("✅ Cancelado."); return ConversationHandler.END