from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DialogStatus(str, enum.Enum):
    NEW = 'new'
    ASSIGNED = 'assigned'
    WAITING_CUSTOMER = 'waiting_customer'
    CLOSED = 'closed'
    MANUAL = 'manual'
    ERROR = 'error'


class MessageDirection(str, enum.Enum):
    INCOMING = 'incoming'
    OUTGOING = 'outgoing'


class OperatorActionType(str, enum.Enum):
    APPROVE = 'approve'
    EDIT = 'edit'
    REJECT = 'reject'


class Dialog(Base):
    __tablename__ = 'dialogs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_chat_id: Mapped[str] = mapped_column(String(255), index=True)
    external_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[DialogStatus] = mapped_column(
        Enum(DialogStatus, name='dialog_status_enum'), default=DialogStatus.NEW, nullable=False, index=True
    )
    assigned_operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list['Message']] = relationship(back_populates='dialog', cascade='all, delete-orphan')

    @property
    def title(self) -> str:
        if self.client_name:
            return self.client_name
        if self.username:
            return f'@{self.username}'
        return self.external_chat_id


class Message(Base):
    __tablename__ = 'messages'
    __table_args__ = (
        UniqueConstraint('dialog_id', 'telegram_message_id', name='uq_messages_dialog_tg_message_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dialog_id: Mapped[int] = mapped_column(ForeignKey('dialogs.id', ondelete='CASCADE'), index=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name='message_direction_enum'), nullable=False, index=True
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dialog: Mapped['Dialog'] = relationship(back_populates='messages')
    ai_suggestions: Mapped[list['AISuggestion']] = relationship(back_populates='message', cascade='all, delete-orphan')
    operator_actions: Mapped[list['OperatorAction']] = relationship(
        back_populates='message', cascade='all, delete-orphan'
    )


class AISuggestion(Base):
    __tablename__ = 'ai_suggestions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey('messages.id', ondelete='CASCADE'), index=True)
    variant_1: Mapped[str] = mapped_column(Text, nullable=False)
    variant_2: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    message: Mapped['Message'] = relationship(back_populates='ai_suggestions')


class OperatorAction(Base):
    __tablename__ = 'operator_actions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey('messages.id', ondelete='CASCADE'), index=True)
    action: Mapped[OperatorActionType] = mapped_column(
        Enum(OperatorActionType, name='operator_action_type_enum'), nullable=False, index=True
    )
    selected_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    message: Mapped['Message'] = relationship(back_populates='operator_actions')
