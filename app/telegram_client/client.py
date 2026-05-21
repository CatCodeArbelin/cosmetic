from pyrogram import Client

from app.telegram_client.handlers import register_handlers


def build_client(name: str, api_id: int, api_hash: str) -> Client:
    return Client(name=name, api_id=api_id, api_hash=api_hash)


def setup_client_handlers(client: Client) -> None:
    register_handlers(client)
