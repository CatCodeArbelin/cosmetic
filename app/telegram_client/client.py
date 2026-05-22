from pathlib import Path

from pyrogram import Client

from app.config import get_settings
from app.telegram_client.handlers import register_handlers


def build_client(name: str, api_id: int, api_hash: str) -> Client:
    settings = get_settings()
    sessions_dir = Path(settings.telegram_session_dir).expanduser()
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return Client(name=name, api_id=api_id, api_hash=api_hash, workdir=str(sessions_dir))


def setup_client_handlers(client: Client) -> None:
    register_handlers(client)
