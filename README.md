# UMMA Tender Bot — Ержан

Telegram-бот "Ержан" — AI-ассистент UMMA Тендер Академии для студентов продукта «Рекорд 1.0».
Отвечает клиентам на казахском языке, помогает новичкам разобраться с тендерами на портале zakup.sk.kz.

## Стек

- Python 3.11+
- [aiogram 3.x](https://docs.aiogram.dev/) — Telegram Bot API
- [Anthropic Claude](https://docs.anthropic.com/) — LLM (по умолчанию `claude-sonnet-4-6`)
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
   - `ANTHROPIC_API_KEY` — ключ с console.anthropic.com
   - `CLAUDE_MODEL` *(опционально)* — по умолчанию `claude-sonnet-4-6`
   - `MAX_HISTORY` *(опционально)* — по умолчанию `20`
4. Railway автоматически запустит деплой. Логи доступны во вкладке **Deployments**.

## Структура

```
bot.py        — основной файл бота (handlers, Claude integration)
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
