"""Channel membership verification handler."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

VERIFIED_KEY = "channel_verified"
_verified_cache = set()
NL = chr(10)


async def require_channel(up: Update, ctx: ContextTypes) -> bool:
    """Check if user joined the required channel. True = can proceed."""
    from config import REQUIRED_CHANNEL
    if not REQUIRED_CHANNEL:
        return True
    uid = up.effective_user.id if up.effective_user else None
    if not uid:
        return False
    if uid in _verified_cache or ctx.user_data.get(VERIFIED_KEY):
        return True
    try:
        member = await ctx.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=uid)
        if member.status in ("member", "administrator", "creator"):
            _verified_cache.add(uid)
            ctx.user_data[VERIFIED_KEY] = True
            return True
    except Exception as e:
        logger.warning("Channel verification check failed: %s", e)
        return True  # allow on error
    return False


async def verify_prompt(up: Update, ctx: ContextTypes):
    """Send a prompt to join the required channel."""
    from config import REQUIRED_CHANNEL
    if not REQUIRED_CHANNEL:
        return
    ch = REQUIRED_CHANNEL.lstrip("@")
    url = "https://t.me/" + ch
    kb = [[InlineKeyboardButton("📢 Ir al canal", url=url)],
           [InlineKeyboardButton("✅ Verificar", callback_data="verify_channel")]]
    text = NL.join([
        "👋 *Bienvenido al Bot Descargador!*",
        "",
        "Para usar el bot, primero debes unirte a nuestro canal:",
        url,
        "",
        "1. Toca el boton de abajo para ir al canal",
        "2. Presiona *Unirse / Join*",
        "3. Vuelve aqui y toca *Verificar*",
    ])
    await up.message.reply_text(text, parse_mode="Markdown",
                                 disable_web_page_preview=True,
                                 reply_markup=InlineKeyboardMarkup(kb))


async def verify_callback(up: Update, ctx: ContextTypes):
    """Handle the verify button callback."""
    q = up.callback_query
    await q.answer()
    ok = await require_channel(up, ctx)
    if ok:
        await q.message.edit_text("✅ *Verificado!*" + NL + NL +
                                   "Ya puedes usar el bot." + NL +
                                   "Envia un enlace de YouTube, TikTok, Facebook, etc.",
                                   parse_mode="Markdown")
        return
    from config import REQUIRED_CHANNEL
    ch = REQUIRED_CHANNEL.lstrip("@")
    url = "https://t.me/" + ch
    kb = [[InlineKeyboardButton("📢 Ir al canal", url=url)],
           [InlineKeyboardButton("🔄 Reintentar", callback_data="verify_channel")]]
    text = NL.join([
        "❌ No estas en el canal.",
        "",
        "1. Toca el boton para ir al canal",
        "2. Presiona *Unirse / Join*",
        "3. Vuelve y toca *Reintentar*",
    ])
    await q.message.edit_text(text, parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(kb))
