"""
Bot de Telegram para descargar videos de YouTube y TikTok.
Punto de entrada principal.
"""

import logging
import os
import threading

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from config import BOT_TOKEN
from handlers.start import start, help_command
from handlers.download import (
    handle_message,
    format_callback,
    cancel,
    SELECTING_FORMAT,
)

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def start_http_server():
    """Servidor HTTP mínimo para health checks de Render."""
    import http.server

    PORT = int(os.environ.get("PORT", 8080))

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot running")

        def log_message(self, format, *args):
            pass  # Silenciar logs del HTTP server

    server = http.server.HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info("Health check server listening on port %s", PORT)
    server.serve_forever()


def main() -> None:
    """Inicializa y arranca el bot."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN no configurado. Revisa el archivo .env")
        return

    # Crear directorio de descargas si no existe
    os.makedirs("downloads", exist_ok=True)

    # Iniciar servidor HTTP en un hilo separado (para Render)
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    # Crear la aplicación
    app = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler para descargas
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            SELECTING_FORMAT: [
                CallbackQueryHandler(format_callback, pattern=r"^yt_"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        ],
    )

    # Registrar handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)

    # Iniciar bot
    logger.info("Bot iniciado. Token: %s...", BOT_TOKEN[:10])
    print("🤖 Bot descargador iniciado.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
