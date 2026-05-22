import asyncio
from contextlib import asynccontextmanager
import logging

from aiogram import Bot, Dispatcher
from fastapi import FastAPI
from pyrogram import Client
from redis.asyncio import Redis

from app.bot.bot import build_bot, build_dispatcher
from app.config import get_settings
from app.db.database import close_database, init_database
from app.logging_config import setup_logging
from app.telegram_client.client import build_client, setup_client_handlers
from app.telegram_client.handlers import bind_bot_for_notifications
from app.telegram_client.sender import bind_client
from app.services.redis_service import bind_redis

settings = get_settings()

bot: Bot | None = None
dispatcher: Dispatcher | None = None
tg_client: Client | None = None
redis_client: Redis | None = None
polling_task: asyncio.Task[None] | None = None
client_started = False

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global bot, dispatcher, tg_client, redis_client, polling_task, client_started

    setup_logging(settings.log_level)
    await init_database(settings.resolved_database_url)

    redis_client = Redis.from_url(settings.redis_url, encoding='utf-8', decode_responses=True)
    await redis_client.ping()
    bind_redis(redis_client)

    bot = build_bot(settings.bot_token.get_secret_value())
    dispatcher = build_dispatcher()
    polling_task = asyncio.create_task(dispatcher.start_polling(bot))

    tg_client = build_client(
        name=settings.pyrogram_session_name,
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash.get_secret_value(),
    )
    setup_client_handlers(tg_client)
    bind_bot_for_notifications(bot)
    bind_client(tg_client)
    try:
        await tg_client.start()
        client_started = True
    except Exception:
        client_started = False
        logger.exception('Failed to start Pyrogram client; continuing without Telegram user client')

    yield

    if tg_client is not None and client_started:
        await tg_client.stop()
    if redis_client is not None:
        await redis_client.close()
    if polling_task is not None:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    if bot is not None:
        await bot.session.close()

    await close_database()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}
