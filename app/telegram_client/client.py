from pathlib import Path

from telethon import TelegramClient

from app.config import get_settings
from app.telegram_client.handlers import register_handlers


def build_client(session_name: str, api_id: int, api_hash: str) -> TelegramClient:
    settings = get_settings()
    sessions_dir = Path(settings.telegram_session_dir).expanduser()
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_path = sessions_dir / session_name
    return TelegramClient(str(session_path), api_id, api_hash)


def setup_client_handlers(client: TelegramClient) -> None:
    register_handlers(client)
