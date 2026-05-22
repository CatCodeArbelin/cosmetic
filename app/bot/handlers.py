from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from app.bot.keyboards import dialog_actions_keyboard, main_keyboard
from app.bot.states import DialogState
from app.config import get_settings
from app.db.database import get_session_factory
from app.db.models import Dialog, DialogStatus, MessageDirection, OperatorActionType
from app.db.repositories import DialogRepository
from app.services.dialog_service import DialogService
from app.telegram_client.sender import send_message

router = Router()
settings = get_settings()
logger = logging.getLogger(__name__)


def _allowed(user_id: int | None) -> bool:
    return bool(user_id and user_id in settings.operator_ids)


async def _deny(message: Message) -> None:
    await message.answer('⛔ Доступ запрещен.')


def _log_ctx(dialog_id: int | str = '-', message_id: int | str = '-', external_chat_id: str = '-', operator_id: int | str = '-', action: str = '-') -> dict[str, int | str]:
    return {'dialog_id': dialog_id, 'message_id': message_id, 'external_chat_id': external_chat_id, 'operator_id': operator_id, 'action': action}


@router.message(Command('start', 'help'))
async def start_handler(message: Message) -> None:
    if not _allowed(message.from_user.id):
        await _deny(message)
        return
    await message.answer('Панель оператора.', reply_markup=main_keyboard())


@router.message(Command('status'))
async def status_handler(message: Message) -> None:
    if not _allowed(message.from_user.id):
        await _deny(message)
        return
    await message.answer(
        f'✅ Бот работает.\nAI: {settings.ai_mode}',
        reply_markup=main_keyboard(),
    )


@router.message(Command('last'))
async def last_handler(message: Message) -> None:
    if not _allowed(message.from_user.id):
        await _deny(message)
        return
    async with get_session_factory()() as session:
        dialogs = await DialogRepository(session).get_new_dialogs(limit=1)
        if not dialogs:
            await message.answer('Нет новых диалогов.')
            return
        dialog = dialogs[0]
        await _render_dialog_card(message, dialog.id)


@router.callback_query(F.data.startswith('dialogs:'))
async def dialogs_nav_handler(callback: CallbackQuery) -> None:
    if not _allowed(callback.from_user.id):
        await callback.answer('Нет доступа', show_alert=True)
        return

    bucket = callback.data.split(':', maxsplit=1)[1]
    async with get_session_factory()() as session:
        repo = DialogRepository(session)
        if bucket == 'new':
            dialogs = await repo.get_new_dialogs()
        elif bucket == 'my':
            dialogs = await repo.get_my_dialogs(callback.from_user.id)
        elif bucket == 'closed':
            dialogs = await repo.get_closed_dialogs()
        else:
            await callback.message.answer(
                f'📈 Статистика\nНовые: {len(await repo.get_new_dialogs(limit=1000))}\n'
                f'Мои: {len(await repo.get_my_dialogs(callback.from_user.id, limit=1000))}\n'
                f'Закрытые: {len(await repo.get_closed_dialogs(limit=1000))}',
                reply_markup=main_keyboard(),
            )
            await callback.answer()
            return

    if not dialogs:
        await callback.message.answer('Список пуст.', reply_markup=main_keyboard())
        await callback.answer()
        return

    for dialog in dialogs[:10]:
        await _render_dialog_card(callback.message, dialog.id)
    await callback.answer()


async def _render_dialog_card(message: Message, dialog_id: int) -> None:
    async with get_session_factory()() as session:
        dialog_service = DialogService(session)
        card_data = await dialog_service.get_dialog_card_data(dialog_id=dialog_id)
        if card_data is None:
            await message.answer('Диалог не найден.')
            return
        dialog = card_data.dialog
        recent_messages = card_data.recent_messages
        suggestion = card_data.suggestion

    header = [
        f'🧾 Диалог #{dialog.id}',
        f'Клиент: {dialog.client_name or "—"}',
        f'Username: @{dialog.username}' if dialog.username else 'Username: —',
    ]

    messages_block = ['\nСообщения:']
    if recent_messages:
        for msg in recent_messages:
            prefix = '📩' if msg.direction == MessageDirection.INCOMING else '📤'
            messages_block.append(f'• {prefix} {(msg.text or "<без текста>").strip() or "<без текста>"}')
    else:
        messages_block.append('• Нет сообщений.')

    ai_block = [
        '\nAI-варианты:',
        f'Вариант 1: {suggestion.variant_1 if suggestion else "—"}',
        f'Вариант 2: {suggestion.variant_2 if suggestion else "—"}',
    ]

    await message.answer(
        '\n'.join(header + messages_block + ai_block),
        reply_markup=dialog_actions_keyboard(dialog.id),
    )


@router.callback_query(F.data.startswith('dialog:'))
async def dialog_action_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if not _allowed(callback.from_user.id):
        await callback.answer('Нет доступа', show_alert=True)
        return

    _, dialog_id_raw, action = callback.data.split(':', maxsplit=2)
    dialog_id = int(dialog_id_raw)

    async with get_session_factory()() as session:
        dialog_service = DialogService(session)
        dialog = await session.get(Dialog, dialog_id)
        if dialog is None:
            await callback.answer('Диалог не найден', show_alert=True)
            return

        if action == 'take':
            assigned_dialog = await dialog_service.assign_operator(dialog_id=dialog_id, operator_id=callback.from_user.id)
            if assigned_dialog is None:
                await callback.message.answer('Диалог уже в работе.')
            else:
                await session.commit()
                logger.info('operator took dialog', extra=_log_ctx(dialog_id=dialog_id, external_chat_id=dialog.external_chat_id, operator_id=callback.from_user.id, action='dialog_taken'))
                await callback.message.answer(f'Диалог #{dialog_id} закреплен за вами.')

        elif action in {'send1', 'send2'}:
            last_incoming, suggestion = await dialog_service.get_last_incoming_with_suggestion(dialog_id=dialog_id)
            text = suggestion.variant_1 if action == 'send1' and suggestion else suggestion.variant_2 if suggestion else 'Спасибо! Мы скоро ответим подробно.'
            logger.info('operator selected reply', extra=_log_ctx(dialog_id=dialog_id, external_chat_id=dialog.external_chat_id, operator_id=callback.from_user.id, action=action))
            sent = await send_message(chat_id=int(dialog.external_chat_id), text=text)
            await dialog_service.save_outgoing_message(dialog=dialog, telegram_message_id=sent.id, raw_payload=sent.model_dump(), text=text)
            if last_incoming:
                await dialog_service.register_operator_action(
                    message_id=last_incoming.id,
                    action=OperatorActionType.APPROVE,
                    operator_id=callback.from_user.id,
                    selected_reply=text,
                )
            await dialog_service.update_status(dialog_id=dialog.id, status=DialogStatus.WAITING_CUSTOMER)
            await session.commit()
            logger.info('outgoing sent to client', extra=_log_ctx(dialog_id=dialog_id, message_id=sent.id, external_chat_id=dialog.external_chat_id, operator_id=callback.from_user.id, action='outgoing_sent'))
            await callback.message.answer('Ответ отправлен клиенту через live-аккаунт.')

        elif action == 'regen':
            last_incoming, _ = await dialog_service.get_last_incoming_with_suggestion(dialog_id=dialog_id)
            if not last_incoming or not (last_incoming.text or '').strip():
                await callback.message.answer('Нет входящего сообщения для регенерации.')
            else:
                new_suggestion = await dialog_service.generate_and_save_ai_suggestion(
                    message=last_incoming,
                    text=last_incoming.text or '',
                )
                await session.commit()
                await callback.message.answer(
                    f'♻️ Сгенерированы новые варианты для сообщения #{last_incoming.id}:\n\n'
                    f'1) {new_suggestion.variant_1}\n\n2) {new_suggestion.variant_2}'
                )

        elif action == 'manual':
            await state.set_state(DialogState.waiting_manual_reply)
            await state.update_data(dialog_id=dialog_id)
            await callback.message.answer('Введите ручной ответ следующим сообщением.')

        elif action == 'close':
            await dialog_service.update_status(dialog_id=dialog_id, status=DialogStatus.CLOSED)
            await session.commit()
            await callback.message.answer(f'Диалог #{dialog_id} закрыт.')

        elif action == 'requeue':
            await dialog_service.requeue_dialog(dialog=dialog)
            await session.commit()
            await callback.message.answer(f'Диалог #{dialog_id} возвращен в очередь.')

        elif action == 'card':
            await _render_dialog_card(callback.message, dialog_id)

    await callback.answer()


@router.message(DialogState.waiting_manual_reply)
async def manual_reply_handler(message: Message, state: FSMContext) -> None:
    if not _allowed(message.from_user.id):
        await _deny(message)
        return

    data = await state.get_data()
    dialog_id = data.get('dialog_id')
    if not dialog_id:
        await message.answer('Не выбран диалог.')
        await state.clear()
        return

    async with get_session_factory()() as session:
        dialog = await session.get(Dialog, dialog_id)
        if dialog is None:
            await message.answer('Диалог не найден.')
            await state.clear()
            return

        text = message.text or ''
        logger.info('operator manual reply selected', extra=_log_ctx(dialog_id=dialog.id, external_chat_id=dialog.external_chat_id, operator_id=message.from_user.id, action='manual_reply'))
        sent = await send_message(chat_id=int(dialog.external_chat_id), text=text)
        dialog_service = DialogService(session)
        await dialog_service.save_outgoing_message(
            dialog=dialog,
            telegram_message_id=sent.id,
            raw_payload=sent.model_dump(),
            text=text,
        )
        last_incoming, _ = await dialog_service.get_last_incoming_with_suggestion(dialog_id=dialog.id)
        if last_incoming:
            await dialog_service.register_operator_action(
                message_id=last_incoming.id,
                action=OperatorActionType.EDIT,
                operator_id=message.from_user.id,
                selected_reply=text,
            )
        await dialog_service.update_status(dialog_id=dialog.id, status=DialogStatus.WAITING_CUSTOMER)
        await session.commit()
        logger.info('outgoing sent to client', extra=_log_ctx(dialog_id=dialog.id, message_id=sent.id, external_chat_id=dialog.external_chat_id, operator_id=message.from_user.id, action='outgoing_sent'))

    await message.answer('Ручной ответ отправлен.')
    await state.clear()
