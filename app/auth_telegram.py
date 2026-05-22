from pathlib import Path

from telethon import TelegramClient

from app.config import get_settings


async def authorize_telegram() -> bool:
    settings = get_settings()

    sessions_dir = Path(settings.telegram_session_dir).expanduser()
    sessions_dir.mkdir(parents=True, exist_ok=True)

    session_path = sessions_dir / settings.telegram_session_name

    print('🔐 Запуск авторизации Telegram-аккаунта...')
    print('Введите код подтверждения Telegram в интерактивном режиме.')

    client = TelegramClient(
        str(session_path),
        settings.telegram_api_id,
        settings.telegram_api_hash.get_secret_value(),
    )

    await client.start(phone=settings.telegram_phone)
    me = await client.get_me()
    print(f'✅ Успешная авторизация: {me.first_name} (id={me.id})')
    print(f'💾 Session-файл сохранен в {sessions_dir}')
    await client.disconnect()
    return True


if __name__ == '__main__':
    import asyncio

    asyncio.run(authorize_telegram())
