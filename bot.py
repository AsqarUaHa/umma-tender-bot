"""
UMMA Tender Academy — Telegram bot "Ержан"
AI-ассистент по тендерам для студентов продукта «Рекорд 1.0».

Runs in WEBHOOK mode so Railway Serverless can scale to zero
and wake up on incoming Telegram updates.
"""

import asyncio
import logging
import os
import re
from typing import Optional

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv
from openai import AsyncOpenAI

from database import Database
from prompt import build_system_prompt
from rag import KnowledgeRAG

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

# Webhook config
PORT = int(os.getenv("PORT", "8080"))
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
db = Database()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
rag = KnowledgeRAG(client=openai_client)


def _clean_markdown(text: str) -> str:
    """Strip markdown formatting that Telegram HTML mode can't render."""
    # **bold** or __bold__ → just the text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # *italic* or _italic_ → just the text
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    # ```code blocks``` → just the text
    text = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).strip('`').strip(), text)
    # `inline code` → just the text
    text = re.sub(r'`(.+?)`', r'\1', text)
    # ### headers → just the text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Leftover standalone * or ** at line start (bullet points)
    text = re.sub(r'^\*\s+', '• ', text, flags=re.MULTILINE)
    return text


WELCOME_TEXT = (
    "Сәлем! 👋\n\n"
    "Мен <b>Ержан</b>, UMMA Тендер Академиясының ИИ-ассистентімін. "
    "«Рекорд 1.0» курсының студенттеріне тендер бойынша көмектесемін.\n\n"
    "Сұрағыңызды жазыңыз, бәрін қарапайым тілмен түсіндіріп беремін 😊\n\n"
    "Командалар:\n"
    "/start — басынан бастау\n"
    "/reset — әңгіме тарихын тазалау\n"
    "/help — көмек"
)

HELP_TEXT = (
    "Мен сізге келесі сұрақтарда көмектесе аламын:\n\n"
    "• ИП ашу, ЭЦП алу\n"
    "• NCLayer орнату\n"
    "• zakup.sk.kz порталына тіркелу\n"
    "• Товарлы тендерлерді іздеу\n"
    "• Тендерге өтінім беру\n"
    "• Ниша таңдау\n\n"
    "Жай ғана сұрағыңызды жазыңыз 😊"
)


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    await db.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    await db.clear_history(user.id)
    await message.answer(WELCOME_TEXT)


@dp.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@dp.message(Command("reset"))
async def handle_reset(message: Message) -> None:
    if message.from_user is None:
        return
    await db.clear_history(message.from_user.id)
    await message.answer("Әңгіме тарихы тазаланды ✅\nЖаңа сұрағыңызды жазыңыз.")


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    user = message.from_user
    if user is None or message.text is None:
        return

    try:
        await db.upsert_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        # RAG: find relevant knowledge for this query
        rag_context = await rag.search(message.text)
        system_prompt = build_system_prompt(rag_context)

        history = await db.get_history(user.id, limit=MAX_HISTORY)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": role, "content": content} for role, content in history)
        messages.append({"role": "user", "content": message.text})

        response = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=1024,
        )
        reply_text = (response.choices[0].message.content or "").strip()
        reply_text = _clean_markdown(reply_text)
        if not reply_text:
            reply_text = "Кешіріңіз, жауап дайындай алмадым. Қайтадан жазып көріңіз 🙏"

        await db.add_message(user.id, "user", message.text)
        await db.add_message(user.id, "assistant", reply_text)

    except Exception as exc:
        logger.exception("Handler error: %s", exc)
        reply_text = (
            "Қазір техникалық ақау болып тұр 😔\n"
            "Сәл күте тұрыңыз немесе кураторға жазыңыз: +7 707 853 2965"
        )

    await message.answer(reply_text)


async def health_check(_request: web.Request) -> web.Response:
    """Health-check endpoint for Railway."""
    return web.Response(text="OK")


async def on_startup(app: web.Application) -> None:
    """Set up webhook and DB on app startup."""
    logger.info("Initializing database...")
    await db.init()

    logger.info("Initializing RAG knowledge base...")
    await rag.init()

    if RAILWAY_PUBLIC_DOMAIN:
        webhook_url = f"https://{RAILWAY_PUBLIC_DOMAIN}{WEBHOOK_PATH}"
        logger.info("Setting webhook: %s", webhook_url)
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=False,
            allowed_updates=dp.resolve_used_update_types(),
        )
    else:
        logger.warning(
            "RAILWAY_PUBLIC_DOMAIN is not set — webhook will not be registered. "
            "Set it in Railway service Settings → Networking → Public Domain."
        )


async def on_shutdown(app: web.Application) -> None:
    """Clean up on shutdown."""
    logger.info("Shutting down...")
    await bot.delete_webhook()
    await db.close()
    await bot.session.close()


def main() -> None:
    """Start the bot in webhook mode behind an aiohttp server."""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    # Register startup / shutdown hooks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Mount the aiogram webhook handler
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)

    logger.info("Starting webhook server on port %d ...", PORT)
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
