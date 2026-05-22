from __future__ import annotations

from typing import Any

from sqlalchemy import Select, exists, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AISuggestion, Dialog, DialogStatus, Message, MessageDirection, OperatorAction, OperatorActionType


class DialogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_by_external_chat_id(self, external_chat_id: str) -> Dialog | None:
        query: Select[tuple[Dialog]] = (
            select(Dialog)
            .where(Dialog.external_chat_id == external_chat_id)
            .where(Dialog.status != DialogStatus.CLOSED)
            .order_by(Dialog.updated_at.desc(), Dialog.id.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_by_external_chat_id(self, external_chat_id: str) -> Dialog | None:
        query: Select[tuple[Dialog]] = (
            select(Dialog)
            .where(Dialog.external_chat_id == external_chat_id)
            .order_by(Dialog.updated_at.desc(), Dialog.id.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_dialog(
        self,
        external_chat_id: str,
        external_user_id: int | None = None,
        client_name: str | None = None,
        username: str | None = None,
        status: DialogStatus = DialogStatus.NEW,
    ) -> Dialog:
        dialog = await self.get_active_by_external_chat_id(external_chat_id)
        if dialog is None:
            dialog = Dialog(
                external_chat_id=external_chat_id,
                external_user_id=external_user_id,
                client_name=client_name,
                username=username,
                status=status,
            )
            self.session.add(dialog)
        else:
            dialog.external_user_id = external_user_id or dialog.external_user_id
            dialog.client_name = client_name or dialog.client_name
            dialog.username = username or dialog.username
            dialog.status = status
        await self.session.flush()
        return dialog

    async def assign_operator(self, dialog_id: int, assigned_operator_id: int) -> Dialog | None:
        query = (
            update(Dialog)
            .where(Dialog.id == dialog_id)
            .where(
                or_(
                    Dialog.assigned_operator_id.is_(None),
                    Dialog.assigned_operator_id == assigned_operator_id,
                )
            )
            .values(assigned_operator_id=assigned_operator_id, status=DialogStatus.ASSIGNED)
            .returning(Dialog)
        )
        result = await self.session.execute(query)
        dialog = result.scalar_one_or_none()
        await self.session.flush()
        return dialog

    async def update_status(self, dialog_id: int, status: DialogStatus) -> Dialog | None:
        dialog = await self.session.get(Dialog, dialog_id)
        if dialog is None:
            return None
        dialog.status = status
        await self.session.flush()
        return dialog

    async def get_new_dialogs(self, limit: int = 50) -> list[Dialog]:
        query = (
            select(Dialog)
            .where(Dialog.status == DialogStatus.NEW)
            .where(Dialog.assigned_operator_id.is_(None))
            .order_by(Dialog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_my_dialogs(self, operator_id: int, limit: int = 50) -> list[Dialog]:
        query = (
            select(Dialog)
            .where(Dialog.assigned_operator_id == operator_id)
            .where(Dialog.status.in_([DialogStatus.ASSIGNED, DialogStatus.WAITING_CUSTOMER, DialogStatus.MANUAL]))
            .order_by(Dialog.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_closed_dialogs(self, limit: int = 50) -> list[Dialog]:
        query = (
            select(Dialog)
            .where(Dialog.status == DialogStatus.CLOSED)
            .order_by(Dialog.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_duplicate(self, external_chat_id: str, telegram_message_id: int) -> bool:
        query = (
            select(
                exists().where(Dialog.id == Message.dialog_id).where(Dialog.external_chat_id == external_chat_id).where(
                    Message.telegram_message_id == telegram_message_id
                )
            )
        )
        result = await self.session.execute(query)
        return bool(result.scalar())

    async def save_message(
        self,
        dialog_id: int,
        external_chat_id: str,
        telegram_message_id: int,
        direction: MessageDirection,
        raw_payload: dict[str, Any],
        text: str | None = None,
    ) -> Message:
        message = Message(
            dialog_id=dialog_id,
            external_chat_id=external_chat_id,
            telegram_message_id=telegram_message_id,
            direction=direction,
            raw_payload=raw_payload,
            text=text,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def save_incoming(
        self,
        dialog_id: int,
        external_chat_id: str,
        telegram_message_id: int,
        raw_payload: dict[str, Any],
        text: str | None = None,
    ) -> Message:
        return await self.save_message(
            dialog_id=dialog_id,
            external_chat_id=external_chat_id,
            telegram_message_id=telegram_message_id,
            direction=MessageDirection.INCOMING,
            raw_payload=raw_payload,
            text=text,
        )

    async def try_register_incoming(
        self,
        dialog_id: int,
        external_chat_id: str,
        telegram_message_id: int,
        raw_payload: dict[str, Any],
        text: str | None = None,
    ) -> Message | None:
        try:
            async with self.session.begin_nested():
                return await self.save_incoming(
                    dialog_id=dialog_id,
                    external_chat_id=external_chat_id,
                    telegram_message_id=telegram_message_id,
                    raw_payload=raw_payload,
                    text=text,
                )
        except IntegrityError:
            return None

    async def save_outgoing(
        self,
        dialog_id: int,
        external_chat_id: str,
        telegram_message_id: int,
        raw_payload: dict[str, Any],
        text: str | None = None,
    ) -> Message:
        return await self.save_message(
            dialog_id=dialog_id,
            external_chat_id=external_chat_id,
            telegram_message_id=telegram_message_id,
            direction=MessageDirection.OUTGOING,
            raw_payload=raw_payload,
            text=text,
        )


class AISuggestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, message_id: int, variant_1: str, variant_2: str, model: str) -> AISuggestion:
        suggestion = AISuggestion(message_id=message_id, variant_1=variant_1, variant_2=variant_2, model=model)
        self.session.add(suggestion)
        await self.session.flush()
        return suggestion


class OperatorActionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        message_id: int,
        action: OperatorActionType,
        operator_id: int,
        selected_reply: str | None = None,
    ) -> OperatorAction:
        item = OperatorAction(
            message_id=message_id,
            action=action,
            operator_id=operator_id,
            selected_reply=selected_reply,
        )
        self.session.add(item)
        await self.session.flush()
        return item
