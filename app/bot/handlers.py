from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import dialog_actions_keyboard, main_keyboard
from app.bot.states import DialogState
from app.config import get_settings
from app.db.database import get_session_factory
from app.db.models import Dialog, DialogStatus, Message as DialogMessage, MessageDirection
from app.db.repositories import DialogRepository, MessageRepository
from app.telegram_client.sender import send_message

router = Router()
settings = get_settings()


def _allowed(user_id: int | None) -> bool:
    return bool(user_id and user_id in settings.operator_ids)


async def _deny(message: Message) -> None:
    await message.answer('⛔ Доступ запрещен.')


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
    await message.answer('✅ Бот работает.', reply_markup=main_keyboard())


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
        await message.answer(
            f'Последний новый диалог #{dialog.id}: {dialog.title or dialog.external_chat_id}',
            reply_markup=dialog_actions_keyboard(dialog.id),
        )


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
        await callback.message.answer(
            f'Диалог #{dialog.id}\nКлиент: {dialog.title or dialog.external_chat_id}\nСтатус: {dialog.status.value}',
            reply_markup=dialog_actions_keyboard(dialog.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith('dialog:'))
async def dialog_action_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if not _allowed(callback.from_user.id):
        await callback.answer('Нет доступа', show_alert=True)
        return

    _, dialog_id_raw, action = callback.data.split(':', maxsplit=2)
    dialog_id = int(dialog_id_raw)

    async with get_session_factory()() as session:
        dialog_repo = DialogRepository(session)
        message_repo = MessageRepository(session)
        dialog = await session.get(Dialog, dialog_id)
        if dialog is None:
            await callback.answer('Диалог не найден', show_alert=True)
            return

        if action == 'take':
            await dialog_repo.assign_operator(dialog_id, callback.from_user.id)
            await session.commit()
            await callback.message.answer(f'Диалог #{dialog_id} закреплен за вами.')

        elif action in {'send1', 'send2'}:
            text = f'Вариант {1 if action == "send1" else 2}: Спасибо! Мы скоро ответим подробно.'
            sent = await send_message(chat_id=int(dialog.external_chat_id), text=text)
            await message_repo.save_outgoing(dialog.id, sent.id, sent.model_dump(), text)
            await dialog_repo.update_status(dialog.id, DialogStatus.WAITING_CUSTOMER)
            await session.commit()
            await callback.message.answer('Ответ отправлен клиенту через live-аккаунт.')

        elif action == 'regen':
            last_incoming = (
                await session.execute(
                    select(DialogMessage)
                    .where(DialogMessage.dialog_id == dialog_id, DialogMessage.direction == MessageDirection.INCOMING)
                    .order_by(DialogMessage.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            await callback.message.answer(f'♻️ Регенерация для сообщения #{last_incoming.id if last_incoming else "-"}.')

        elif action == 'manual':
            await state.set_state(DialogState.waiting_manual_reply)
            await state.update_data(dialog_id=dialog_id)
            await callback.message.answer('Введите ручной ответ следующим сообщением.')

        elif action == 'close':
            await dialog_repo.update_status(dialog_id, DialogStatus.CLOSED)
            await session.commit()
            await callback.message.answer(f'Диалог #{dialog_id} закрыт.')

        elif action == 'requeue':
            dialog.operator_id = None
            await dialog_repo.update_status(dialog_id, DialogStatus.NEW)
            await session.commit()
            await callback.message.answer(f'Диалог #{dialog_id} возвращен в очередь.')

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
        sent = await send_message(chat_id=int(dialog.external_chat_id), text=text)
        await MessageRepository(session).save_outgoing(dialog.id, sent.id, sent.model_dump(), text)
        await DialogRepository(session).update_status(dialog.id, DialogStatus.WAITING_CUSTOMER)
        await session.commit()

    await message.answer('Ручной ответ отправлен.')
    await state.clear()
