import time
import json
import os
import requests
from bs4 import BeautifulSoup
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])

PLAYLIST_URL = "https://soundcloud.com/usuario/sets/mi-playlist"
CHECK_INTERVAL_SECONDS = 300  # cada 5 minutos

STATE_FILE = "playlist_state.json"


def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()


def fetch_playlist_tracks():
    """
    Devuelve una lista de 'tracks' (por ejemplo una lista de strings con títulos).
    Aquí hacemos scraping simple del HTML público de la playlist.
    Si SoundCloud cambia el HTML, habria que ajustar los selectores.
    """
    resp = requests.get(PLAYLIST_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Esto es aproximado: buscamos meta tags JSON con info de la playlist
    # o elementos con data-track.
    tracks = []

    # Intento 1: buscar en el script JSON (Open Graph / ld+json)
    # Si no, al menos capturamos los títulos visibles en la página.
    for meta in soup.find_all("meta"):
        if meta.get("itemprop") == "name":
            # Esto puede pillar cosas extra, filtraremos luego si hace falta
            content = meta.get("content", "").strip()
            if content and "playlist" not in content.lower():
                tracks.append(content)

    # Quitar duplicados manteniendo orden
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
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data.get("tracks", [])
        except json.JSONDecodeError:
            return []


def save_state(tracks):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"tracks": tracks}, f, ensure_ascii=False, indent=2)


def main():
    print("Chequeando playlist de SoundCloud una vez...")

    previous_tracks = load_previous_state()
    current_tracks = fetch_playlist_tracks()

    if not previous_tracks:
        save_state(current_tracks)
        print(f"Estado inicial guardado con {len(current_tracks)} pistas.")
        return

    new_tracks = [t for t in current_tracks if t not in previous_tracks]

    if new_tracks:
        for track in new_tracks:
            msg = f"🎵 Nueva canción añadida a la playlist:\n{track}\n\n{PLAYLIST_URL}"
            send_telegram_message(msg)
            print("Notificado:", track)

        save_state(current_tracks)
    else:
        print("Sin nuevas canciones.")


if __name__ == "__main__":
    main()
