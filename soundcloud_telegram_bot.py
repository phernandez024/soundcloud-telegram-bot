import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === CONFIGURACIÓN ===
PLAYLIST_URL = "https://soundcloud.com/doncucho/sets/prueba"
STATE_FILE = "playlist_state.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Falta variable de entorno TELEGRAM_BOT_TOKEN")

# Logging útil para ver qué pasa
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# === LÓGICA DE SOUNDCloud ===

def fetch_playlist_tracks():
    """
    Devuelve una lista de títulos de canciones de la playlist.
    OJO: este scraping es muy aproximado; quizá tengas que adaptarlo
    a cómo SoundCloud renderiza tu playlist.
    """
    resp = requests.get(PLAYLIST_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    tracks = []

    # Ejemplo sencillo: buscar tags <meta itemprop="name">
    for meta in soup.find_all("meta"):
        if meta.get("itemprop") == "name":
            title = meta.get("content", "").strip()
            # Filtrar cosas obvias que no sean canciones si lo necesitas
            if title and "playlist" not in title.lower():
                tracks.append(title)

    # Quitar duplicados manteniendo el orden
    seen = set()
    unique_tracks = []
    for t in tracks:
        if t not in seen:
            seen.add(t)
            unique_tracks.append(t)

    return unique_tracks


def load_previous_state():
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("tracks", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_state(tracks):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"tracks": tracks}, f, ensure_ascii=False, indent=2)


def check_playlist_once():
    """
    Comprueba la playlist UNA vez.
    Devuelve (new_tracks, current_tracks):
      - new_tracks: lista de canciones nuevas detectadas.
      - current_tracks: lista completa actual.
    """
    previous_tracks = load_previous_state()
    current_tracks = fetch_playlist_tracks()

    # Primera vez: guardamos estado y no avisamos de todo
    if not previous_tracks:
        save_state(current_tracks)
        logger.info("Estado inicial guardado con %d pistas.", len(current_tracks))
        return [], current_tracks

    new_tracks = [t for t in current_tracks if t not in previous_tracks]

    if new_tracks:
        # Actualizamos estado sólo si hay cambios
        save_state(current_tracks)

    return new_tracks, current_tracks


# === HANDLERS DE TELEGRAM ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola 👋\n"
        "Soy tu bot de SoundCloud.\n"
        "Usa /check para comprobar si hay nuevas canciones en la playlist."
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info("Comando /check recibido desde chat %s", chat_id)

    await update.message.reply_text("🔍 Comprobando la playlist de SoundCloud...")

    try:
        new_tracks, current_tracks = check_playlist_once()
    except Exception as e:
        logger.exception("Error comprobando la playlist")
        await update.message.reply_text(f"❌ Error comprobando la playlist: {e}")
        return

    if not current_tracks:
        await update.message.reply_text(
            "No he podido encontrar pistas en la playlist. "
            "¿Seguro que la URL es correcta?"
        )
        return

    if new_tracks:
        # Mandamos un mensaje por cada nueva canción
        for track in new_tracks:
            text = (
                "🎵 Nueva canción detectada en la playlist:\n"
                f"{track}\n\n"
                f"Playlist: {PLAYLIST_URL}"
            )
            await update.message.reply_text(text)
    else:
        await update.message.reply_text("✅ No hay nuevas canciones desde la última vez.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponibles:\n"
        "/start - info del bot\n"
        "/check - comprobar la playlist\n"
        "/help - ver esta ayuda"
    )


# === MAIN ===

async def main():
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Registramos comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("help", help_cmd))

    # Inicia el bot y se queda escuchando mensajes
    await application.run_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
