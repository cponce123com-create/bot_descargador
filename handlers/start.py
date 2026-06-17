"""
Handlers de comandos basicos: /start y /help.
"""

from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de bienvenida."""
    text = "🎬 *Bot Descargador*\n\nEnvíame un enlace de **YouTube** o **TikTok** y lo descargaré para ti.\n\nEjemplos:\n• `https://youtube.com/watch?v=...`\n• `https://youtu.be/...`\n• `https://tiktok.com/@user/video/...`\n• `https://vm.tiktok.com/...`\n\nUsa /help para mas informacion."
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de ayuda detallado."""
    text = "📖 *Ayuda*\n\n*YouTube:*\n• Envia cualquier enlace de YouTube\n• Elige entre video (varias calidades) o solo audio\n• Limite: 50MB por archivo\n\n*TikTok:*\n• Envia cualquier enlace de TikTok\n• Se descarga SIN marca de agua\n• Si falla, se intenta con marca de agua\n\n*Limites:*\n• Videos >50MB no pueden enviarse por Telegram\n• Para YouTube, puedes elegir solo audio en ese caso\n\n¿Dudas? @tu_soporte (opcional)"
    await update.message.reply_text(text, parse_mode="Markdown")
