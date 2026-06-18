"""Inline mode handler."""

import uuid
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ContextTypes

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja las consultas inline."""
    query = update.inline_query.query
    if not query:
        return

    # Si el usuario pega una URL, ofrecemos la opción de descargarla
    # Nota: El bot necesita que el usuario le envíe la URL en un chat privado para procesarla,
    # pero el modo inline puede servir como un acceso directo o para compartir info.
    
    results = [
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="📥 Descargar Multimedia",
            description=f"Haz clic para procesar: {query}",
            input_message_content=InputTextMessageContent(query),
        )
    ]

    await update.inline_query.answer(results)
