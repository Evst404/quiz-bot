import json
import os
import random
import re
from enum import IntEnum
from typing import Any

import redis
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)


def get_quiz_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Новый вопрос", "Сдаться"], ["Мой счёт"]],
        resize_keyboard=True,
    )


def normalize_answer(text: str) -> str:
    text = re.split(r"[.(]", text)[0]
    text = re.sub(r'[.,!?;:"\'()–—-]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Привет! Я бот для викторины!\n"
        "Нажми «Новый вопрос», чтобы начать!",
        reply_markup=get_quiz_keyboard(),
    )
    return States.IDLE


def handle_new_question_request(update: Update, context: CallbackContext, questions: list, r: Any) -> int:
    question = random.choice(questions)
    user_id = str(update.effective_user.id)

    r.set(f"user:{user_id}:current_question", json.dumps(question))
    r.set(f"user:{user_id}:attempts", 0)

    update.message.reply_text(
        f"<b>Вопрос:</b>\n\n{question['question']}",
        parse_mode="HTML",
        reply_markup=get_quiz_keyboard(),
    )
    return States.QUESTION_ACTIVE


def handle_solution_attempt(update: Update, context: CallbackContext, r: Any) -> int:
    user_id = str(update.effective_user.id)
    cur_json = r.get(f"user:{user_id}:current_question")
    if not cur_json:
        return States.IDLE

    question = json.loads(cur_json)
    user_norm = normalize_answer(update.message.text)
    correct_norm = normalize_answer(question["answer"])

    attempts = int(r.get(f"user:{user_id}:attempts") or 0) + 1
    r.set(f"user:{user_id}:attempts", attempts)

    if user_norm == correct_norm:
        update.message.reply_text(
            "Правильно! Поздравляю! \n"
            "Нажми «Новый вопрос» для продолжения.",
            reply_markup=get_quiz_keyboard(),
        )
        score = int(r.get(f"user:{user_id}:score") or 0) + 1
        r.set(f"user:{user_id}:score", score)
        r.delete(f"user:{user_id}:current_question")
        r.delete(f"user:{user_id}:attempts")
        return States.AFTER_ANSWER

    if attempts >= 2:
        hint = question["answer"].split(".")[0].split("(")[0].strip()
        update.message.reply_text(
            f"Неправильно… Попробуешь ещё раз?\n\n"
            f"<i>Подсказка:</i> {hint[:15]}...",
            parse_mode="HTML",
            reply_markup=get_quiz_keyboard(),
        )
    else:
        update.message.reply_text(
            "Неправильно… Попробуешь ещё раз?",
            reply_markup=get_quiz_keyboard(),
        )

    total = int(r.get(f"user:{user_id}:total") or 0) + 1
    r.set(f"user:{user_id}:total", total)
    return States.QUESTION_ACTIVE


def surrender(update: Update, context: CallbackContext, r: Any) -> int:
    user_id = str(update.effective_user.id)
    cur_json = r.get(f"user:{user_id}:current_question")
    if cur_json:
        q = json.loads(cur_json)
        update.message.reply_text(
            f"Вы сдались!\n\n"
            f"<b>Правильный ответ:</b> {q['answer']}\n\n"
            f"Нажми «Новый вопрос» для продолжения.",
            parse_mode="HTML",
            reply_markup=get_quiz_keyboard(),
        )
        r.delete(f"user:{user_id}:current_question")
        r.delete(f"user:{user_id}:attempts")
        return States.AFTER_ANSWER
    update.message.reply_text("Вы ещё не начали викторину!")
    return States.IDLE


def my_score(update: Update, context: CallbackContext, r: Any) -> int:
    user_id = str(update.effective_user.id)
    score = int(r.get(f"user:{user_id}:score") or 0)
    total = int(r.get(f"user:{user_id}:total") or 0)
    percent = (score / total * 100) if total > 0 else 0
    update.message.reply_text(
        f"<b>Ваш счёт:</b>\n"
        f"{score} из {total} ({percent:.0f}%)",
        parse_mode="HTML",
        reply_markup=get_quiz_keyboard(),
    )
    return States.QUESTION_ACTIVE if r.get(f"user:{user_id}:current_question") else States.IDLE


class States(IntEnum):
    IDLE = 0
    QUESTION_ACTIVE = 1
    AFTER_ANSWER = 2


def main() -> None:
    load_dotenv()

    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не найден в .env")

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
    REDIS_DB = int(os.getenv("REDIS_DB", 0))

    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        decode_responses=True,
    )

    with open("questions.json", "r", encoding="utf-8") as f:
        QUESTIONS = json.load(f)

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.IDLE: [
                MessageHandler(Filters.regex("^Новый вопрос$"), lambda u, c: handle_new_question_request(u, c, QUESTIONS, r)),
                MessageHandler(Filters.regex("^Мой счёт$"), lambda u, c: my_score(u, c, r)),
            ],
            States.QUESTION_ACTIVE: [
                MessageHandler(Filters.regex("^Сдаться$"), lambda u, c: surrender(u, c, r)),
                MessageHandler(Filters.regex("^Новый вопрос$"), lambda u, c: u.message.reply_text(
                    "Сначала закончи текущий вопрос!", reply_markup=get_quiz_keyboard()
                ) or States.QUESTION_ACTIVE),
                MessageHandler(Filters.regex("^Мой счёт$"), lambda u, c: my_score(u, c, r)),
                MessageHandler(Filters.text & ~Filters.command, lambda u, c: handle_solution_attempt(u, c, r)),
            ],
            States.AFTER_ANSWER: [
                MessageHandler(Filters.regex("^Новый вопрос$"), lambda u, c: handle_new_question_request(u, c, QUESTIONS, r)),
                MessageHandler(Filters.regex("^Мой счёт$"), lambda u, c: my_score(u, c, r)),
                MessageHandler(Filters.regex("^Сдаться$"), lambda u, c: u.message.reply_text(
                    "Вы уже закончили вопрос!", reply_markup=get_quiz_keyboard()
                ) or States.AFTER_ANSWER),
            ],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
    )

    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()