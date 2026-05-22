from telethon import TelegramClient
from telethon.tl.custom.message import Message


def bind_client(client: TelegramClient) -> None:
    setattr(send_message_to_client, '_client', client)


async def send_message_to_client(chat_id: int, text: str) -> Message:
    client: TelegramClient | None = getattr(send_message_to_client, '_client', None)
    if client is None:
        raise RuntimeError('Telethon client is not bound')
    return await client.send_message(entity=chat_id, message=text)


# backward compatibility
send_message = send_message_to_client
