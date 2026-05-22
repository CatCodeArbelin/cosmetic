from pathlib import Path

from pyrogram import Client

from app.config import get_settings


def authorize_telegram() -> bool:
    settings = get_settings()

    sessions_dir = Path(settings.telegram_session_dir).expanduser()
    sessions_dir.mkdir(parents=True, exist_ok=True)

    print('🔐 Запуск авторизации Telegram-аккаунта...')
    print('Введите номер телефона и код подтверждения Telegram в интерактивном режиме.')

    with Client(
        name=settings.pyrogram_session_name,
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash.get_secret_value(),
        workdir=str(sessions_dir),
    ) as client:
        me = client.get_me()
        print(f'✅ Успешная авторизация: {me.first_name} (id={me.id})')

    print(f'💾 Session-файл сохранен в {sessions_dir}')
    return True


if __name__ == '__main__':
    authorize_telegram()
