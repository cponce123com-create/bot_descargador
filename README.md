# Bot Descargador 🤖

Bot de Telegram para descargar videos de **YouTube** y **TikTok sin marca de agua**.

## Características

- ✅ Descarga videos de YouTube (elige calidad o solo audio)
- ✅ Descarga videos de TikTok **sin marca de agua** (vía TikWM API)
- ✅ Fallback a yt-dlp si la API de TikTok falla
- ✅ Menú inline interactivo para elegir formato
- ✅ Manejo del límite de 50MB de Telegram
- ✅ Limpieza automática de archivos temporales

## Requisitos

- Python 3.11+
- ffmpeg (para procesar audio de YouTube)
- Token de bot de Telegram (de [@BotFather](https://t.me/BotFather))

## Instalación

```bash
# Clonar el repositorio
git clone <tu-repo>
cd bot-descargador

# Crear entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar token
echo "BOT_TOKEN=tu_token_aqui" > .env
```

## Uso

```bash
python3 bot.py
```

## Comandos del bot

| Comando | Descripción |
|---------|------------|
| `/start` | Mensaje de bienvenida |
| `/help`  | Ayuda detallada |
| Enviar URL de YouTube | Muestra menú para elegir formato |
| Enviar URL de TikTok | Descarga directa sin marca de agua |

## Estructura del proyecto

```
bot-descargador/
├── bot.py                 # Punto de entrada
├── config.py              # Configuración
├── handlers/
│   ├── start.py           # /start y /help
│   └── download.py        # Lógica de descarga
├── services/
│   ├── youtube.py         # YouTube con yt-dlp
│   ├── tiktok.py          # TikTok sin watermark (TikWM API)
│   └── file_utils.py      # Utilidades de archivos
├── downloads/             # Archivos temporales
├── requirements.txt
├── .env                   # Token del bot (no subir a git)
└── .gitignore
```

## Deploy en Render

1. Crea un nuevo **Web Service** en Render
2. Conecta tu repositorio de GitHub
3. Configura:
   - **Start Command:** `python3 bot.py`
   - **Environment Variable:** `BOT_TOKEN` con tu token
4. Render instalará automáticamente desde `requirements.txt`

## Tecnologías

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20.x
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [TikWM API](https://tikwm.com) (TikTok sin watermark)
- Python 3.11+
