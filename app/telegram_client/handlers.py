from __future__ import annotations

import asyncio
import json
import logging

from aiogram import Bot
from telethon import TelegramClient, events
from telethon.tl.custom.message import Message as TgMessage

from app.config import get_settings
from app.db.database import get_session_factory
from app.db.models import Dialog
from app.services.dialog_service import DialogService
from app.services.redis_service import get_redis

settings = get_settings()
logger = logging.getLogger(__name__)
_flush_tasks: dict[str, asyncio.Task[None]] = {}


def _log_ctx(dialog_id: int | str = '-', message_id: int | str = '-', external_chat_id: str = '-', operator_id: int | str = '-', action: str = '-') -> dict[str, int | str]:
    return {'dialog_id': dialog_id, 'message_id': message_id, 'external_chat_id': external_chat_id, 'operator_id': operator_id, 'action': action}


async def _process_incoming_message(message: TgMessage) -> None:
    if message.out or message.post:
        return
    if message.chat_id == 777000:
        return
    if not message.sender_id:
        return

    text = (message.text or '').strip()
    external_chat_id = str(message.chat_id)
    redis = get_redis()

    dedupe_key = f'msg:processed:{external_chat_id}:{message.id}'
    if not await redis.set(dedupe_key, '1', ex=3600, nx=True):
        logger.warning('duplicate incoming ignored', extra=_log_ctx(message_id=message.id, external_chat_id=external_chat_id, action='incoming_deduplicated'))
        return

    await redis.rpush(buffer_key := f'msg:buffer:{external_chat_id}', json.dumps({'id': message.id, 'text': text, 'payload': message.to_dict()}))
    logger.info('incoming received', extra=_log_ctx(message_id=message.id, external_chat_id=external_chat_id, action='incoming_received'))
    await redis.expire(buffer_key, max(60, settings.incoming_debounce_seconds * 5))

    await redis.set(f'fsm:dialog:{external_chat_id}', 'collecting', ex=300)
    await redis.set(f'fsm:dialog_last_ts:{external_chat_id}', str(message.date.timestamp()), ex=300)
    await _schedule_flush(external_chat_id)


async def _schedule_flush(external_chat_id: str) -> None:
    existing_task = _flush_tasks.get(external_chat_id)
    if existing_task and not existing_task.done():
        existing_task.cancel()
    task = asyncio.create_task(_flush_after_debounce(external_chat_id))
    _flush_tasks[external_chat_id] = task


async def _flush_after_debounce(external_chat_id: str) -> None:
    try:
        await asyncio.sleep(settings.incoming_debounce_seconds)
        await _flush_buffer(external_chat_id)
    except asyncio.CancelledError:
        return
    finally:
        current = _flush_tasks.get(external_chat_id)
        if current is asyncio.current_task():
            _flush_tasks.pop(external_chat_id, None)


async def _flush_buffer(external_chat_id: str) -> None:
    redis = get_redis()
    flush_lock_key = f'msg:flush_lock:{external_chat_id}'
    if not await redis.set(flush_lock_key, '1', ex=30, nx=True):
        return

    buffer_key = f'msg:buffer:{external_chat_id}'
    try:
        raw_items = await redis.lrange(buffer_key, 0, -1)
        if not raw_items:
            return
        items = [json.loads(raw) for raw in raw_items]
        await redis.delete(buffer_key)
        await redis.set(f'fsm:dialog:{external_chat_id}', 'ready_for_ai', ex=300)
        combined_text = '\n'.join(item.get('text', '') for item in items if item.get('text'))
        latest = items[-1]

        session_factory = get_session_factory()
        async with session_factory() as session:
            dialog_service = DialogService(session)
            user_payload = latest.get('payload', {}).get('sender', {}) or {}
            dialog = await dialog_service.get_or_create_active_dialog(
                external_chat_id=external_chat_id,
                external_user_id=user_payload.get('user_id'),
                client_name=user_payload.get('first_name'),
                username=user_payload.get('username'),
            )
            saved_messages, trigger_message, combined_text = await dialog_service.save_incoming_batch(dialog=dialog, external_chat_id=external_chat_id, items=items)
            if not saved_messages:
                return
            await dialog_service.generate_and_save_ai_suggestion(message=trigger_message, text=combined_text)
            await session.commit()
        await _notify_operators(dialog_id=dialog.id, dialog_title=dialog.title, text=combined_text, message_id=trigger_message.id)
    finally:
        await redis.delete(flush_lock_key)


async def _notify_operators(dialog_id: int, dialog_title: str | None, text: str | None, message_id: int) -> None:
    bot: Bot | None = getattr(_notify_operators, 'bot', None)
    if bot is None:
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        dialog = await session.get(Dialog, dialog_id)
        assigned_operator_id = dialog.assigned_operator_id if dialog else None
    recipients = [assigned_operator_id] if assigned_operator_id else settings.operator_ids
    for operator_id in recipients:
        await bot.send_message(chat_id=operator_id, text=f'📩 Новое сообщение\nДиалог: {dialog_title or "Клиент"} (ID: {dialog_id})\nТекст: {(text or "<без текста>")[:300]}\nID сообщения: {message_id}')


def bind_bot_for_notifications(bot: Bot) -> None:
    setattr(_notify_operators, 'bot', bot)


def register_handlers(client: TelegramClient) -> None:
    @client.on(events.NewMessage(incoming=True))
    async def _on_private_message(event: events.NewMessage.Event) -> None:
        if not event.is_private:
            return
        await _process_incoming_message(event.message)
