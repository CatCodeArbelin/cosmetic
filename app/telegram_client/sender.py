from pyrogram import Client
from pyrogram.types import Message


def bind_client(client: Client) -> None:
    setattr(send_message, '_client', client)


async def send_message(chat_id: int, text: str) -> Message:
    client: Client | None = getattr(send_message, '_client', None)
    if client is None:
        raise RuntimeError('Pyrogram client is not bound')
    return await client.send_message(chat_id=chat_id, text=text)
