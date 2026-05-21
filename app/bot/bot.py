from aiogram import Bot, Dispatcher

from app.bot.handlers import router


def build_bot(token: str) -> Bot:
    return Bot(token=token)


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher
