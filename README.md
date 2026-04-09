# UMMA Tender Bot — Ержан

Telegram-бот "Ержан" — AI-ассистент UMMA Тендер Академии для студентов продукта «Рекорд 1.0».
Отвечает клиентам на казахском языке, помогает новичкам разобраться с тендерами на портале zakup.sk.kz.

## Стек

- Python 3.11+
- [aiogram 3.x](https://docs.aiogram.dev/) — Telegram Bot API
- [OpenAI](https://platform.openai.com/) — LLM (по умолчанию `gpt-4o-mini`)
- MySQL (через `aiomysql`) — хранение пользователей и истории диалогов
- Railway — деплой

## Локальный запуск

```bash
pip install -r requirements.txt
cp .env.example .env
# заполните BOT_TOKEN, ANTHROPIC_API_KEY и параметры MySQL
python bot.py
```

## Деплой на Railway

1. Создайте новый проект на [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → выберите этот репозиторий.
2. Добавьте MySQL плагин: **New** → **Database** → **Add MySQL**. Railway автоматически создаст переменные `MYSQL_URL`, `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE`.
3. В сервисе бота откройте **Variables** и добавьте:
   - `BOT_TOKEN` — токен от @BotFather
   - `OPENAI_API_KEY` — ключ с platform.openai.com
   - `OPENAI_MODEL` *(опционально)* — по умолчанию `gpt-4o-mini`
   - `MAX_HISTORY` *(опционально)* — по умолчанию `20`
4. Railway автоматически запустит деплой. Логи доступны во вкладке **Deployments**.

## Структура

```
bot.py        — основной файл бота (handlers, OpenAI integration)
database.py   — MySQL слой (aiomysql, pool, schema)
prompt.py     — системный промпт Ержана
requirements.txt
Procfile
railway.json
.env.example
```

## Команды бота

- `/start` — приветствие, очистка истории
- `/help` — список возможностей
- `/reset` — очистить контекст диалога
