"""
Handlers de comandos basicos: /start, /help y /cookies.
"""

import os
import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

COOKIES_FILE = os.path.abspath("cookies.txt")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de bienvenida."""
    text = "\U0001f3ac *Bot Descargador*\n\nEnviame un enlace de **YouTube** o **TikTok** y lo descargare para ti.\n\nEjemplos:\n\u2022 `https://youtube.com/watch?v=...`\n\u2022 `https://youtu.be/...`\n\u2022 `https://tiktok.com/@user/video/...`\n\u2022 `https://vm.tiktok.com/...`\n\nUsa /help para mas informacion."
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de ayuda detallado."""
    text = "\U0001f4d6 *Ayuda*\n\n*YouTube:*\n\u2022 Envia cualquier enlace de YouTube\n\u2022 Elige entre video (varias calidades) o solo audio\n\u2022 Limite: 300MB por archivo\n\n*TikTok:*\n\u2022 Envia cualquier enlace de TikTok\n\u2022 Se descarga SIN marca de agua\n\u2022 Si falla, se intenta con marca de agua\n\n*Limites:*\n\u2022 Videos >300MB no pueden enviarse por Telegram\n\u2022 Para YouTube, puedes elegir solo audio en ese caso\n\n*Cookies de YouTube:*\n\u2022 Usa /cookies para enviar tus cookies y evitar bloqueos de YouTube"
    await update.message.reply_text(text, parse_mode="Markdown")


async def cookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recibe un archivo cookies.txt de YouTube para usar en las descargas."""
    if not update.message.document:
        text = (
            "\U0001f36a *Cookies de YouTube*\n\n"
            + "Para descargar videos de YouTube necesito tus cookies. "
            + "Asi evito el bloqueo *\"Sign in to confirm you\'re not a bot\"*.\n\n"
            + "*Pasos:*\n"
            + "1. Instala una extension como *Get cookies.txt* "
            + "([Chrome](https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid) "
            + "| [Firefox](https://addons.mozilla.org/es/firefox/addon/cookies-txt/))\n"
            + "2. Ve a YouTube y asegurate de estar logueado\n"
            + "3. Haz clic en la extension y exporta las cookies\n"
            + "4. Envia el archivo *cookies.txt* con el comando:\n"
            + "   `/cookies` (adjuntando el archivo)\n\n"
            + "Las cookies se guardan solo para esta sesion y son necesarias "
            + "porque YouTube bloquea las IPs de servicios cloud como Render."
        )
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
        return

    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        await update.message.reply_text("\u274c Envia un archivo `.txt` con las cookies.")
        return

    try:
        file = await doc.get_file()
        await file.download_to_drive(COOKIES_FILE)

        with open(COOKIES_FILE) as f:
            content_check = f.read()

        if "# Netscape HTTP Cookie File" not in content_check and ".youtube.com" not in content_check:
            os.remove(COOKIES_FILE)
            await update.message.reply_text(
                "\u274c El archivo no tiene formato valido de cookies. "
                "Asegurate de exportarlas correctamente con la extension."
            )
            return

        size = len(content_check)
        # Log formato para debug
        first_line = content_check.split("\n")[0] if content_check else "(vacio)"
        logger.info("Cookies OK: %d bytes, formato: %s, tiene .youtube.com: %s",
                     size, first_line[:80], ".youtube.com" in content_check)
        await update.message.reply_text(
            f"\u2705 *Cookies guardadas correctamente*\n\n"
            + f"Archivo: {size} bytes\n"
            + "Ahora puedes descargar videos de YouTube sin bloqueos.\n\n"
            + "*Importante:* Las cookies expiran con el tiempo. "
            + "Si vuelves a ver el error, repite el proceso.",
            parse_mode="Markdown",
        )
        logger.info("Cookies de YouTube guardadas (%d bytes)", size)

    except Exception as e:
        logger.error("Error guardando cookies: %s", e)
        await update.message.reply_text(
            "\u274c Error al guardar las cookies. Intenta de nuevo."
        )
