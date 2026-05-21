from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.keyboards import main_keyboard

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer('Бот запущен.', reply_markup=main_keyboard())
