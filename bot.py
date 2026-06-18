"""
Bot de Telegram para descargar videos.
Punto de entrada principal.
"""
import asyncio
import logging
import os
import sys
import threading
import traceback

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PicklePersistence,
    filters,
)
from telegram.ext._basepersistence import PersistenceInput

from config import BOT_TOKEN, ALLOWED_USER_IDS
from handlers.start import start, help_command, cookies_command
from handlers.download import (
    handle_message,
    handle_search,
    handle_generic_download,
    format_callback,
    cancel,
    SELECTING_FORMAT,
)

logger = logging.getLogger(__name__)


async def global_error_handler(up: Update, ctx):
    """Log all unhandled errors and notify the user."""
    logger.exception("Unhandled error: %s", ctx.error)
    tb = "".join(traceback.format_exception(None, ctx.error, ctx.error.__traceback__))
    logger.error("Traceback:\n%s", tb)
    if up and up.effective_message:
        try:
            await up.effective_message.reply_text("❌ Ocurrio un error, intenta de nuevo.")
        except Exception:
            pass

# Global concurrency limiter: max 2 concurrent downloads (safe for a small VPS).
# Acquired in handlers that call yt-dlp/ffmpeg subprocesses.
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)


def start_http_server():
    """Servidor HTTP para health checks de Render."""
    import http.server

    PORT = int(os.environ.get("PORT", 8080))

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot running")

        def log_message(self, fmt, *args):
            pass

    try:
        server = http.server.HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info("Health check server listening on port %s", PORT)
        sys.stdout.flush()
        server.serve_forever()
    except Exception as e:
        logger.error("HTTP server error: %s", e)
        sys.stdout.flush()


async def _auth_guard(up: Update, ctx) -> bool:
    """Reject updates from unauthorized users. Returns False if blocked."""
    if ALLOWED_USER_IDS is None:
        return True  # no restrictions
    uid = up.effective_user.id if up.effective_user else None
    if uid and uid in ALLOWED_USER_IDS:
        return True
    # Silently ignore unauthorized users (no reply to avoid leaking the bot)
    logger.info("Blocked update from uid=%s", uid)
    return False


async def orphan_callback(up: Update, ctx):
    """Maneja callbacks cuando el estado del ConversationHandler se pierde."""
    if not await _auth_guard(up, ctx):
        return
    q = up.callback_query
    await q.answer()
    await q.message.reply_text(
        "La sesion expiro. Envia el enlace de nuevo para descargar."
    )


def main() -> None:
    """Inicializa el bot con persistencia de estado."""
    try:
        if not BOT_TOKEN:
            msg = "BOT_TOKEN no configurado."
            logger.error(msg)
            print(msg, file=sys.stderr)
            sys.stderr.flush()
            sys.exit(1)

        os.makedirs("downloads", exist_ok=True)

        http_thread = threading.Thread(target=start_http_server, daemon=True)
        http_thread.start()

        import time
        time.sleep(0.5)

        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
            stream=sys.stdout,
        )

        store_input = PersistenceInput(user_data=True, chat_data=True, bot_data=False)
        persistence = PicklePersistence(
            filepath="bot_data.pkl",
            store_data=store_input,
            on_flush=True,
        )

        logger.info("Inicializando bot...")
        app = (
            Application.builder()
            .token(BOT_TOKEN)
            .persistence(persistence)
            .build()
        )

        # Make semaphore accessible to handlers
        app.bot_data["download_sem"] = DOWNLOAD_SEMAPHORE

        conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            states={
                SELECTING_FORMAT: [
                    CallbackQueryHandler(format_callback, pattern=r"^yt_"),
                    CallbackQueryHandler(handle_generic_download, pattern=r"^gen_"),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
                CallbackQueryHandler(orphan_callback, pattern=r"^(yt_|gen_)"),
            ],
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("search", handle_search))
        app.add_handler(CommandHandler("cookies", cookies_command))
        app.add_handler(conv_handler)
        app.add_handler(MessageHandler(filters.Document.ALL, cookies_command))

        # Register global error handler
        app.add_error_handler(global_error_handler)

        logger.info("Bot conectandose a Telegram...")
        sys.stdout.flush()
        print("Bot descargador iniciado.", flush=True)
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

    except Exception as e:
        logger.exception("Error fatal: %s", e)
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
