from __future__ import annotations

import json
import logging
import asyncio

from aiogram import Bot
from pyrogram import Client, filters
from pyrogram.types import Message as TgMessage

from app.config import get_settings
from app.db.database import get_session_factory
from app.db.models import Dialog, DialogStatus
from app.db.repositories import AISuggestionRepository, DialogRepository, MessageRepository
from app.services.ai_service import AIService
from app.services.redis_service import get_redis

settings = get_settings()
logger = logging.getLogger(__name__)
_flush_tasks: dict[str, asyncio.Task[None]] = {}


async def _process_incoming_message(message: TgMessage) -> None:
    if message.outgoing or message.service:
        return
    if not message.from_user or message.from_user.is_bot:
        return

    text = (message.text or message.caption or '').strip()
    external_chat_id = str(message.chat.id)
    redis = get_redis()

    dedupe_key = f'msg:processed:{external_chat_id}:{message.id}'
    if not await redis.set(dedupe_key, '1', ex=3600, nx=True):
        return

    buffer_key = f'msg:buffer:{external_chat_id}'
    await redis.rpush(buffer_key, json.dumps({'id': message.id, 'text': text, 'payload': message.model_dump()}))
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
            dialog_repo = DialogRepository(session)
            message_repo = MessageRepository(session)

            dialog = await dialog_repo.get_by_external_chat_id(external_chat_id)
            user_payload = latest.get('payload', {}).get('from_user', {})
            external_user_id = user_payload.get('id')
            first_name = user_payload.get('first_name') or ''
            last_name = user_payload.get('last_name') or ''
            client_name = (f'{first_name} {last_name}'.strip() or None)
            username = user_payload.get('username')

            if dialog is None:
                dialog = await dialog_repo.upsert_dialog(
                    external_chat_id=external_chat_id,
                    external_user_id=external_user_id,
                    client_name=client_name,
                    username=username,
                    status=DialogStatus.NEW,
                )
            elif dialog.status == DialogStatus.CLOSED:
                dialog = await dialog_repo.update_status(dialog.id, DialogStatus.NEW) or dialog

            saved_message = await message_repo.save_incoming(
                dialog_id=dialog.id,
                telegram_message_id=int(latest['id']),
                raw_payload={'batched_messages': [i.get('payload', {}) for i in items]},
                text=combined_text,
            )

            ai_service = AIService(settings.openai_api_key.get_secret_value(), settings.openai_model)
            v1, v2 = await ai_service.generate_variants(combined_text)
            await AISuggestionRepository(session).save(saved_message.id, v1, v2, settings.openai_model)

            await session.commit()

        await redis.set(f'fsm:dialog:{external_chat_id}', 'queued_for_operator', ex=600)
        await _notify_operators(dialog_id=dialog.id, dialog_title=dialog.title, text=combined_text, message_id=saved_message.id)
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
    if not recipients:
        return

    preview = (text or '<без текста>').strip()
    if len(preview) > 300:
        preview = f'{preview[:300]}…'

    title = dialog_title or 'Клиент'
    msg = f'📩 Новое сообщение\nДиалог: {title} (ID: {dialog_id})\nТекст: {preview}\nID сообщения: {message_id}'
    for operator_id in recipients:
        try:
            await bot.send_message(chat_id=operator_id, text=msg)
        except Exception:
            logger.exception('Failed to notify operator %s', operator_id)


def bind_bot_for_notifications(bot: Bot) -> None:
    setattr(_notify_operators, 'bot', bot)


def register_handlers(client: Client) -> None:
    @client.on_message(filters.private & ~filters.outgoing)
    async def _on_private_message(_: Client, message: TgMessage) -> None:
        await _process_incoming_message(message)
