from __future__ import annotations

from aiogram import Bot
from pyrogram import Client, filters
from pyrogram.types import Message as TgMessage

from app.config import get_settings
from app.db.database import get_session_factory
from app.db.models import Dialog, DialogStatus
from app.db.repositories import DialogRepository, MessageRepository

settings = get_settings()


async def _process_incoming_message(message: TgMessage) -> None:
    if message.outgoing or message.service:
        return
    if not message.from_user or message.from_user.is_bot:
        return

    text = message.text or message.caption
    external_chat_id = str(message.chat.id)

    session_factory = get_session_factory()
    async with session_factory() as session:
        dialog_repo = DialogRepository(session)
        message_repo = MessageRepository(session)

        if await message_repo.is_duplicate(external_chat_id=external_chat_id, telegram_message_id=message.id):
            return

        dialog = await dialog_repo.get_by_external_chat_id(external_chat_id)
        title = message.from_user.full_name

        if dialog is None:
            dialog = await dialog_repo.upsert_dialog(external_chat_id=external_chat_id, title=title, status=DialogStatus.NEW)
        elif dialog.status == DialogStatus.CLOSED:
            dialog = await dialog_repo.update_status(dialog.id, DialogStatus.NEW) or dialog

        saved_message = await message_repo.save_incoming(
            dialog_id=dialog.id,
            telegram_message_id=message.id,
            raw_payload=message.model_dump(),
            text=text,
        )
        await session.commit()

    await _notify_operators(dialog_id=dialog.id, dialog_title=dialog.title, text=text, message_id=saved_message.id)


async def _notify_operators(dialog_id: int, dialog_title: str | None, text: str | None, message_id: int) -> None:
    bot: Bot | None = getattr(_notify_operators, 'bot', None)
    if bot is None:
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        dialog = await session.get(Dialog, dialog_id)
        assigned_operator_id = dialog.operator_id if dialog else None

    recipients = [assigned_operator_id] if assigned_operator_id else settings.operator_ids
    if not recipients:
        return

    preview = (text or '<без текста>').strip()
    if len(preview) > 300:
        preview = f'{preview[:300]}…'

    title = dialog_title or 'Клиент'
    msg = f'📩 Новое сообщение\nДиалог: {title} (ID: {dialog_id})\nТекст: {preview}\nID сообщения: {message_id}'
    for operator_id in recipients:
        await bot.send_message(chat_id=operator_id, text=msg)


def bind_bot_for_notifications(bot: Bot) -> None:
    setattr(_notify_operators, 'bot', bot)


def register_handlers(client: Client) -> None:
    @client.on_message(filters.private & ~filters.outgoing)
    async def _on_private_message(_: Client, message: TgMessage) -> None:
        await _process_incoming_message(message)
