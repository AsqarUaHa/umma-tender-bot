"""
UMMA Tender Academy — Telegram bot "Ержан"
AI-ассистент по тендерам для студентов продукта «Рекорд 1.0».
"""

import asyncio
import logging
import os
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from database import Database
from prompt import SYSTEM_PROMPT

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY is not set")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
db = Database()
claude = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


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

    await db.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    history = await db.get_history(user.id, limit=MAX_HISTORY)
    messages = [{"role": role, "content": content} for role, content in history]
    messages.append({"role": "user", "content": message.text})

    try:
        response = await claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        reply_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if not reply_text:
            reply_text = "Кешіріңіз, жауап дайындай алмадым. Қайтадан жазып көріңіз 🙏"
    except Exception as exc:
        logger.exception("Claude API error: %s", exc)
        reply_text = (
            "Қазір техникалық ақау болып тұр 😔\n"
            "Сәл күте тұрыңыз немесе кураторға жазыңыз: +7 707 853 2965"
        )
        await message.answer(reply_text)
        return

    await db.add_message(user.id, "user", message.text)
    await db.add_message(user.id, "assistant", reply_text)

    await message.answer(reply_text)


async def main() -> None:
    logger.info("Initializing database...")
    await db.init()
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
