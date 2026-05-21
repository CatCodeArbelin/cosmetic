from pyrogram import Client


async def send_message(client: Client, chat_id: int, text: str) -> None:
    await client.send_message(chat_id=chat_id, text=text)
