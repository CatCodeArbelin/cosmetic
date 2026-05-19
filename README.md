Сделай production MVP AI-помощника для менеджеров косметического магазина.

Цель проекта:
Система должна помогать менеджерам быстрее отвечать клиентам в Telegram.

Клиенты пишут в существующий живой Telegram-аккаунт магазина, например “Елизавета”.
Система читает входящие сообщения этого аккаунта, анализирует их, генерирует AI-варианты ответов и отправляет карточку менеджеру в отдельный Telegram-бот.
Менеджер выбирает готовый ответ или пишет свой.
Ответ клиенту должен уходить от имени живого Telegram-аккаунта магазина “Елизавета”, а не от имени бота.

Стек:
- Python 3.11+
- Pyrogram для работы с живым Telegram-аккаунтом магазина
- aiogram 3 для Telegram-бота менеджера
- FastAPI
- PostgreSQL
- Redis
- OpenAI API
- Docker
- docker-compose
- python-dotenv
- SQLAlchemy 2.x

Обязательное требование запуска:
Проект должен запускаться командой:

docker compose up --build

README должен содержать подробную инструкцию:
- как создать Telegram-бота через BotFather;
- как получить BOT_TOKEN;
- как узнать MANAGER_CHAT_ID;
- как получить Telegram API_ID и API_HASH;
- как авторизовать живой Telegram-аккаунт магазина;
- как получить OPENAI_API_KEY;
- как заполнить .env;
- как запустить проект;
- как проверить работу.

Логика работы:

1. Живой Telegram-аккаунт магазина

Есть аккаунт магазина, например “Елизавета”.
Клиенты пишут этому аккаунту в личные сообщения.

Pyrogram должен:
- авторизоваться как этот аккаунт;
- слушать новые входящие личные сообщения;
- игнорировать исходящие сообщения;
- игнорировать сообщения от сервисного Telegram-бота;
- сохранять сообщения в PostgreSQL;
- вызывать AI;
- отправлять карточку менеджеру в Telegram-бот.

Важно:
Не использовать Telegram forward.
Нужно создавать красивую отдельную карточку диалога.

2. Telegram-бот менеджера

Бот работает через aiogram.

Команды:
- /start
- /help
- /status
- /last

/start:

“AI-помощник менеджера запущен.

Система подключена к Telegram-аккаунту магазина.
Новые сообщения клиентов будут приходить сюда.”

Когда приходит сообщение клиента:

📩 Новое сообщение

Клиент: Анна
Telegram: @username или id

Сообщение:
“Здравствуйте! Нужен уход для сухой кожи 35+, что можете посоветовать?”

AI предлагает:

Вариант 1:
...

Вариант 2:
...

Кнопки:
[✅ Отправить 1]
[✅ Отправить 2]
[🔄 Сгенерировать заново]
[✍️ Ответить вручную]
[👤 Взять без AI]

3. Отправка ответа клиенту

Если менеджер нажимает “Отправить 1”:
- система берет AI-вариант;
- отправляет сообщение клиенту через Pyrogram;
- сообщение отправляется от имени живого Telegram-аккаунта магазина;
- обновляется статус диалога;
- менеджеру приходит:
“✅ Ответ отправлен клиенту.”

Аналогично для “Отправить 2”.

Если менеджер нажимает “Ответить вручную”:
- бот пишет:
“✍️ Напишите ответ следующим сообщением.”
- следующее сообщение менеджера считается ручным ответом;
- система отправляет его клиенту;
- статус обновляется.

Если менеджер нажимает “Взять без AI”:
- статус диалога становится manual_taken;
- бот пишет:
“Диалог отмечен как ручной.”

4. AI-модуль

Использовать OpenAI API.

Модель по умолчанию:

gpt-4.1-mini

Через .env:

OPENAI_MODEL=gpt-4.1-mini

AI должен:
- генерировать 2 коротких варианта ответа;
- учитывать историю диалога;
- учитывать базу знаний;
- учитывать правила общения магазина.

System prompt:

Ты AI-помощник менеджера магазина профессиональной косметики.
Ты НЕ отвечаешь клиенту напрямую.
Ты предлагаешь менеджеру 2 коротких варианта ответа.

Правила:
- русский язык;
- обращение на “вы”;
- дружелюбный стиль;
- без давления;
- без медицинских обещаний;
- нельзя обещать лечение заболеваний;
- нельзя гарантировать результат;
- если мало информации — задавай уточняющие вопросы.

OpenAI желательно просить вернуть JSON:

{
  "variant_1": "...",
  "variant_2": "..."
}

Если OpenAI недоступен или ответ сломан:
использовать fallback-ответы.

5. База знаний

Создать:

app/knowledge_base.md

Разделы:
- правила общения;
- сухая кожа;
- чувствительная кожа;
- возрастной уход;
- доставка;
- оплата;
- график работы.

Пока без embeddings и RAG.

Но knowledge_service.py должен быть отдельным сервисом, чтобы потом можно было расширить.

6. Интеграция с МойСклад

Сделать архитектурную подготовку.

Создать:

moysklad_service.py

.env:

MOYSKLAD_ENABLED=false
MOYSKLAD_TOKEN=
MOYSKLAD_BASE_URL=https://api.moysklad.ru/api/remap/1.2

Если MOYSKLAD_ENABLED=false:
- AI работает без МойСклад.

Если true:
- реализовать простой поиск товара;
- получать:
  - название;
  - цену;
  - остаток;
  - артикул.

Если API МойСклад недоступен:
- логировать ошибку;
- не падать.

7. PostgreSQL

Использовать PostgreSQL.

Таблицы:

dialogs:
- id
- external_chat_id
- external_user_id
- client_name
- username
- status
- created_at
- updated_at

messages:
- id
- dialog_id
- direction
- text
- raw_payload JSONB
- created_at

ai_suggestions:
- id
- message_id
- variant_1
- variant_2
- model
- created_at

operator_actions:
- id
- message_id
- action
- selected_reply
- manager_chat_id
- created_at

Статусы:
- new
- ai_generated
- sent
- manual_pending
- manual_sent
- manual_taken
- error

8. Redis

Redis использовать:
- для FSM;
- временных состояний;
- защиты от дублей.

9. Защита от дублей

Не обрабатывать одно и то же сообщение дважды.

Сохранять:
- external_chat_id
- telegram_message_id

10. Логи

Логировать:
- запуск сервисов;
- подключение Telegram;
- входящие сообщения;
- генерацию AI;
- отправку ответа;
- ошибки OpenAI;
- ошибки Pyrogram;
- ошибки БД.

11. .env.example

# Telegram bot
BOT_TOKEN=
MANAGER_CHAT_ID=

# Telegram account
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
PYROGRAM_SESSION_NAME=cosmetic_store

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini

# PostgreSQL
POSTGRES_DB=cosmetic_ai
POSTGRES_USER=cosmetic_ai
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql+asyncpg://cosmetic_ai:change_me@postgres:5432/cosmetic_ai

# Redis
REDIS_URL=redis://redis:6379/0

# App
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO

# MoySklad
MOYSKLAD_ENABLED=false
MOYSKLAD_TOKEN=
MOYSKLAD_BASE_URL=https://api.moysklad.ru/api/remap/1.2

12. Авторизация Telegram-аккаунта

Сделать:

app/auth_telegram.py

Команда:

docker compose run --rm app python -m app.auth_telegram

Скрипт должен:
- запросить код Telegram;
- создать session-файл Pyrogram;
- сохранить его в volume.

docker-compose должен содержать:

./sessions:/app/sessions

13. Docker Compose

docker-compose.yml:

services:
- app
- postgres
- redis

Команда запуска:

docker compose up --build

Все должно стартовать автоматически.

14. README

README на русском языке.

Разделы:
1. Что делает система
2. Архитектура
3. Что входит в MVP
4. Что НЕ входит
5. Как создать Telegram-бота
6. Как получить API_ID/API_HASH
7. Как авторизовать Telegram-аккаунт
8. Как получить OpenAI API key
9. Как заполнить .env
10. Как запустить docker compose up --build
11. Как проверить работу
12. Как смотреть логи
13. Частые ошибки
14. Как сделать backup базы
15. Как подключить МойСклад позже

15. Структура проекта

app/
  __init__.py
  main.py
  config.py
  logging_config.py

  bot/
    __init__.py
    bot.py
    handlers.py
    keyboards.py
    states.py

  telegram_client/
    __init__.py
    client.py
    handlers.py
    sender.py

  services/
    __init__.py
    ai_service.py
    knowledge_service.py
    moysklad_service.py
    dialog_service.py

  db/
    __init__.py
    database.py
    models.py
    repositories.py

  auth_telegram.py
  knowledge_base.md

.env.example
requirements.txt
Dockerfile
docker-compose.yml
README.md

16. Ограничения MVP

Не делать:
- веб-панель;
- CRM;
- WazzUp;
- голосовые;
- изображения;
- auto-reply без менеджера;
- сложный RAG;
- аналитику;
- роли;
- оплату.

17. Важные требования

- Все настройки только через .env
- Без токенов в коде
- Не падать при ошибках OpenAI
- Не падать при ошибках МойСклад
- AI только предлагает варианты
- Ответ клиенту отправляет живой Telegram-аккаунт
- Telegram-бот — только операторская панель

18. Финальный результат

После запуска:

cp .env.example .env
# заполнить .env
docker compose run --rm app python -m app.auth_telegram
docker compose up --build

Система должна:
- ловить сообщения клиентов;
- отправлять карточки менеджеру;
- генерировать AI-варианты;
- отправлять выбранный ответ клиенту от имени живого аккаунта магазина.
