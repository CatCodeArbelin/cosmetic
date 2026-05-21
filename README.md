# Cosmetic Support AI MVP

Production-ready MVP AI-помощника для менеджеров косметического магазина. Система принимает входящие сообщения клиентов в живой Telegram-аккаунт магазина, предлагает варианты ответов менеджеру через Telegram-бота и отправляет ответ клиенту от имени аккаунта магазина.

## 1) О проекте и цель

- Цель: ускорить работу менеджеров и стандартизировать клиентскую коммуникацию.
- Клиенты пишут в личные сообщения живого аккаунта (через Pyrogram).
- Менеджер получает карточку диалога в боте (aiogram) и выбирает действие.
- AI генерирует 2 варианта ответа через OpenAI API.

## 2) Архитектура и стек

- Python 3.11+
- FastAPI
- Pyrogram + TgCrypto
- aiogram 3
- PostgreSQL
- Redis
- OpenAI API
- Docker / Docker Compose

Сервисы в `docker-compose.yml`:
- `app`
- `postgres`
- `redis`

## 3) Структура окружения и переменные `.env`

1. Скопируйте шаблон:
   ```bash
   cp .env.example .env
   ```
2. Заполните обязательные значения:
   - Telegram bot/account (включая `TELEGRAM_PHONE`, `PYROGRAM_SESSION_NAME`)
   - OpenAI
   - PostgreSQL
   - Redis
   - app/debounce

См. полный шаблон в `.env.example`.

## 4) Создание Telegram-бота через BotFather

1. Откройте `@BotFather`.
2. Выполните `/newbot`.
3. Задайте имя и username.
4. Сохраните токен.
5. Внесите токен в `.env` как `BOT_TOKEN`.

## 5) Как узнать `MANAGER_CHAT_ID`

Варианты:
- Добавьте временный echo-хендлер в бота, отправьте `/start`, прочитайте `chat.id` из логов.
- Используйте `getUpdates` для бота и возьмите `message.chat.id`.

Затем внесите значение в `MANAGER_CHAT_ID` и/или `OPERATOR_IDS`.

## 6) Получение Telegram `API_ID` и `API_HASH`

1. Перейдите на https://my.telegram.org.
2. Войдите с номером телефона аккаунта магазина.
3. Откройте **API development tools**.
4. Создайте приложение и получите:
   - `API_ID`
   - `API_HASH`
5. Заполните `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` в `.env`.

## 7) Авторизация живого Telegram-аккаунта (Pyrogram)

Выполните:
```bash
docker compose run --rm app python -m app.auth_telegram
```

Что происходит:
- интерактивный ввод номера телефона и кода Telegram;
- при успешном входе session-файл (`PYROGRAM_SESSION_NAME`) сохраняется в `/app/sessions`;
- на хосте это volume `./sessions`.

## 8) Получение `OPENAI_API_KEY`

1. Создайте ключ в кабинете OpenAI.
2. Добавьте в `.env`:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL` (по умолчанию `gpt-4.1-mini`)

## 9) PostgreSQL и Redis конфигурация

Используются переменные:
- PostgreSQL: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `DATABASE_URL`
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_URL`

Сервисы имеют healthcheck и restart policy.

## 10) Запуск проекта

Обязательная команда запуска:
```bash
docker compose up --build
```

Фоновой режим:
```bash
docker compose up -d --build
```

## 11) Проверка работоспособности

Минимальные проверки:
```bash
docker compose ps
docker compose logs -f app
```

Ожидаемо:
- `app`, `postgres`, `redis` в статусе `healthy`/`running`;
- у `app` запущен `uvicorn` на `0.0.0.0:8000`.

## 12) Логи и мониторинг

Полезные команды:
```bash
docker compose logs -f app
docker compose logs -f postgres
docker compose logs -f redis
```

Проверка авторизации Telegram:
- если сессия не создана, повторите `python -m app.auth_telegram`.

## 13) Частые ошибки и решения

1. **`TELEGRAM_API_ID`/`TELEGRAM_API_HASH` invalid**
   - Проверьте значения из `my.telegram.org`.
2. **`BOT_TOKEN` invalid**
   - Сгенерируйте новый токен в BotFather.
3. **OpenAI 401/429**
   - Проверьте ключ, квоты и лимиты.
4. **Не подключается к PostgreSQL/Redis**
   - Проверьте `DATABASE_URL`, `REDIS_URL`, статус контейнеров.
5. **Нет session-файла Pyrogram**
   - Запустите авторизацию заново и убедитесь в наличии volume `./sessions:/app/sessions`.

## 14) Резервное копирование PostgreSQL

Создать backup:
```bash
docker compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

Восстановить backup:
```bash
cat backup.sql | docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

Рекомендуется хранить бэкапы вне хоста и настраивать расписание.

## 15) Масштабирование и production-практики

- Добавьте reverse proxy (Nginx/Traefik).
- Используйте managed PostgreSQL и Redis.
- Вынесите секреты в Secret Manager.
- Настройте централизованные логи и алерты.
- Масштабируйте `app` горизонтально (несколько реплик), учитывая конкуренцию за обновления/очереди.
- Для больших нагрузок добавьте очередь задач (например, Celery/RQ) и worker-процессы.

---

## Быстрый старт

```bash
cp .env.example .env
mkdir -p sessions
docker compose run --rm app python -m app.auth_telegram
docker compose up --build
```
