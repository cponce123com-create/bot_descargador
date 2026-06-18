"""
Bot de Telegram para descargar videos de YouTube y TikTok.
Punto de entrada principal.
"""

import logging
import os
import sys
import threading

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    InlineQueryHandler,
    filters,
)

from config import BOT_TOKEN
from handlers.start import start, help_command, cookies_command
from handlers.download import (
    handle_message,
    handle_search,
    handle_generic_download,
    format_callback,
    cancel,
    SELECTING_FORMAT,
)
from handlers.inline import inline_query

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
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

        def log_message(self, fmt, *args):
            pass  # Silenciar logs del HTTP server

    try:
        server = http.server.HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info("Health check server listening on port %s", PORT)
        sys.stdout.flush()
        server.serve_forever()
    except Exception as e:
        logger.error("HTTP server error: %s", e)
        sys.stdout.flush()


def main() -> None:
    """Inicializa y arranca el bot."""
    try:
        if not BOT_TOKEN:
            msg = "BOT_TOKEN no configurado. Agrega la variable de entorno en Render."
            logger.error(msg)
            print(msg, file=sys.stderr)
            sys.stderr.flush()
            sys.exit(1)

        # Crear directorio de descargas
        os.makedirs("downloads", exist_ok=True)

        # Iniciar servidor HTTP primero (para Render)
        http_thread = threading.Thread(target=start_http_server, daemon=True)
        http_thread.start()

        # Pequeña pausa para que el servidor HTTP se inicie
        import time
        time.sleep(0.5)

        # Crear la aplicación
        logger.info("Inicializando bot...")
        app = Application.builder().token(BOT_TOKEN).build()

        # ConversationHandler para descargas
        conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
            states={
                SELECTING_FORMAT: [
                    CallbackQueryHandler(format_callback, pattern=r"^yt_"),
                    CallbackQueryHandler(handle_generic_download, pattern=r"^gen_"),
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
        app.add_handler(CommandHandler("search", handle_search))
        app.add_handler(CommandHandler("cookies", cookies_command))
        app.add_handler(conv_handler)
        # Handler para archivos .txt (cookies enviadas sin /cookies)
        app.add_handler(MessageHandler(filters.Document.ALL, cookies_command))
        # Handler para modo inline
        app.add_handler(InlineQueryHandler(inline_query))

        # Iniciar bot
        logger.info("Bot conectandose a Telegram...")
        sys.stdout.flush()
        print("🤖 Bot descargador iniciado.", flush=True)
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.exception("Error fatal al iniciar el bot: %s", e)
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
