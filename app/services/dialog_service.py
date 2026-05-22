from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AISuggestion, Dialog, DialogStatus, Message, MessageDirection, OperatorActionType
from app.db.repositories import AISuggestionRepository, DialogRepository, MessageRepository, OperatorActionRepository
from app.services.ai_service import AIService

settings = get_settings()


def _latest_suggestion_query(message_id: int):
    return (
        select(AISuggestion)
        .where(AISuggestion.message_id == message_id)
        .order_by(AISuggestion.created_at.desc())
        .limit(1)
    )


@dataclass(slots=True)
class DialogCardData:
    dialog: Dialog
    recent_messages: list[Message]
    suggestion: AISuggestion | None


class DialogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.dialog_repo = DialogRepository(session)
        self.message_repo = MessageRepository(session)
        self.ai_suggestion_repo = AISuggestionRepository(session)
        self.operator_action_repo = OperatorActionRepository(session)

    async def get_or_create_active_dialog(
        self,
        *,
        external_chat_id: str,
        external_user_id: int | None,
        client_name: str | None,
        username: str | None,
    ) -> Dialog:
        dialog = await self.dialog_repo.get_active_by_external_chat_id(external_chat_id)
        if dialog is None:
            latest_dialog = await self.dialog_repo.get_latest_by_external_chat_id(external_chat_id)
            if latest_dialog is not None and latest_dialog.status == DialogStatus.CLOSED:
                dialog = Dialog(
                    external_chat_id=external_chat_id,
                    external_user_id=external_user_id,
                    client_name=client_name,
                    username=username,
                    status=DialogStatus.NEW,
                )
                self.session.add(dialog)
                await self.session.flush()
            else:
                dialog = await self.dialog_repo.upsert_dialog(
                    external_chat_id=external_chat_id,
                    external_user_id=external_user_id,
                    client_name=client_name,
                    username=username,
                    status=DialogStatus.NEW,
                )
        return dialog

    async def save_incoming_batch(
        self,
        *,
        dialog: Dialog,
        external_chat_id: str,
        items: list[dict],
    ) -> tuple[list[Message], Message | None, str]:
        if not items:
            return [], None, ''
        combined_text = '\n'.join(item.get('text', '') for item in items if item.get('text'))
        trigger_telegram_message_id = int(items[-1]['id'])
        saved_messages: list[Message] = []
        batch_size = len(items)
        for index, item in enumerate(items, start=1):
            telegram_message_id = int(item['id'])
            is_trigger = telegram_message_id == trigger_telegram_message_id
            saved_item = await self.message_repo.try_register_incoming(
                dialog_id=dialog.id,
                external_chat_id=external_chat_id,
                telegram_message_id=telegram_message_id,
                raw_payload={
                    'payload': item.get('payload', {}),
                    'batch': {
                        'size': batch_size,
                        'position': index,
                        'trigger_telegram_message_id': trigger_telegram_message_id,
                        'is_trigger': is_trigger,
                    },
                },
                text=item.get('text'),
            )
            if saved_item is not None:
                saved_messages.append(saved_item)
        trigger_message = saved_messages[-1] if saved_messages else None
        return saved_messages, trigger_message, combined_text

    async def save_outgoing_message(
        self,
        *,
        dialog: Dialog,
        telegram_message_id: int,
        raw_payload: dict,
        text: str | None,
    ) -> Message:
        return await self.message_repo.save_outgoing(
            dialog.id, dialog.external_chat_id, telegram_message_id, raw_payload, text
        )

    async def assign_operator(self, *, dialog_id: int, operator_id: int) -> Dialog | None:
        return await self.dialog_repo.assign_operator(dialog_id, operator_id)

    async def update_status(self, *, dialog_id: int, status: DialogStatus) -> Dialog | None:
        return await self.dialog_repo.update_status(dialog_id, status)

    async def requeue_dialog(self, *, dialog: Dialog) -> Dialog:
        dialog.assigned_operator_id = None
        await self.dialog_repo.update_status(dialog.id, DialogStatus.NEW)
        return dialog

    async def generate_and_save_ai_suggestion(self, *, message: Message, text: str) -> AISuggestion:
        ai_service = AIService(settings.openai_api_key.get_secret_value(), settings.openai_model)
        v1, v2 = await ai_service.generate_variants(text, dialog_id=message.dialog_id, message_id=message.id, external_chat_id=message.external_chat_id)
        return await self.ai_suggestion_repo.save(message.id, v1, v2, settings.openai_model)

    async def register_operator_action(
        self, *, message_id: int, action: OperatorActionType, operator_id: int, selected_reply: str | None = None
    ):
        return await self.operator_action_repo.save(message_id, action, operator_id, selected_reply)

    async def get_dialog_card_data(self, *, dialog_id: int, messages_limit: int = 5) -> DialogCardData | None:
        dialog = await self.session.get(Dialog, dialog_id)
        if dialog is None:
            return None
        recent_messages = (
            await self.session.execute(
                select(Message)
                .where(Message.dialog_id == dialog_id)
                .order_by(Message.created_at.desc())
                .limit(messages_limit)
            )
        ).scalars().all()
        latest_incoming = next((msg for msg in recent_messages if msg.direction == MessageDirection.INCOMING), None)
        suggestion = (
            await self.session.execute(_latest_suggestion_query(latest_incoming.id))
        ).scalar_one_or_none() if latest_incoming else None
        return DialogCardData(dialog=dialog, recent_messages=list(recent_messages), suggestion=suggestion)

    async def get_last_incoming_with_suggestion(self, *, dialog_id: int) -> tuple[Message | None, AISuggestion | None]:
        last_incoming = (
            await self.session.execute(
                select(Message)
                .where(Message.dialog_id == dialog_id, Message.direction == MessageDirection.INCOMING)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        suggestion = (
            await self.session.execute(_latest_suggestion_query(last_incoming.id))
        ).scalar_one_or_none() if last_incoming else None
        return last_incoming, suggestion
