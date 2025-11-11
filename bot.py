import json
import os
import random
import re
from enum import IntEnum

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)


class States(IntEnum):
    IDLE = 0
    QUESTION_ACTIVE = 1
    AFTER_ANSWER = 2


def get_quiz_keyboard():
    return ReplyKeyboardMarkup(
        [["Новый вопрос", "Сдаться"], ["Мой счёт"]],
        resize_keyboard=True,
    )


def get_quiz_keyboard_after_answer():
    return ReplyKeyboardMarkup(
        [["Новый вопрос"], ["Мой счёт"]],
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


def handle_new_question_request(update: Update, context: CallbackContext, questions, redis_client) -> int:
    question = random.choice(questions)
    user_id = f"tg-{update.effective_user.id}"

    redis_client.set(f"{user_id}:current_question", json.dumps(question))
    redis_client.set(f"{user_id}:attempts", 0)

    update.message.reply_text(
        f"<b>Вопрос:</b>\n\n{question['question']}",
        parse_mode="HTML",
        reply_markup=get_quiz_keyboard(),
    )
    return States.QUESTION_ACTIVE


def handle_solution_attempt(update: Update, context: CallbackContext, redis_client) -> int:
    user_id = f"tg-{update.effective_user.id}"
    current_question_json = redis_client.get(f"{user_id}:current_question")
    if not current_question_json:
        return States.IDLE

    question = json.loads(current_question_json)
    user_answer_normalized = normalize_answer(update.message.text)
    correct_answer_normalized = normalize_answer(question["answer"])

    attempts = int(redis_client.get(f"{user_id}:attempts") or 0) + 1
    redis_client.set(f"{user_id}:attempts", attempts)

    if user_answer_normalized == correct_answer_normalized:
        update.message.reply_text(
            "Правильно! Поздравляю!\n"
            "Нажми «Новый вопрос» для продолжения.",
            reply_markup=get_quiz_keyboard_after_answer(),
        )
        score = int(redis_client.get(f"{user_id}:score") or 0) + 1
        redis_client.set(f"{user_id}:score", score)
        redis_client.delete(f"{user_id}:current_question")
        redis_client.delete(f"{user_id}:attempts")
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

    total = int(redis_client.get(f"{user_id}:total") or 0) + 1
    redis_client.set(f"{user_id}:total", total)
    return States.QUESTION_ACTIVE


def surrender(update: Update, context: CallbackContext, redis_client) -> int:
    user_id = f"tg-{update.effective_user.id}"
    current_question_json = redis_client.get(f"{user_id}:current_question")
    if current_question_json:
        question = json.loads(current_question_json)
        update.message.reply_text(
            f"Вы сдались!\n\n"
            f"<b>Правильный ответ:</b> {question['answer']}\n\n"
            f"Нажми «Новый вопрос» для продолжения.",
            parse_mode="HTML",
            reply_markup=get_quiz_keyboard_after_answer(),
        )
        redis_client.delete(f"{user_id}:current_question")
        redis_client.delete(f"{user_id}:attempts")
        return States.AFTER_ANSWER
    update.message.reply_text("Вы ещё не начали викторину!")
    return States.IDLE


def my_score(update: Update, context: CallbackContext, redis_client) -> int:
    user_id = f"tg-{update.effective_user.id}"
    score = int(redis_client.get(f"{user_id}:score") or 0)
    total = int(redis_client.get(f"{user_id}:total") or 0)
    percent = (score / total * 100) if total > 0 else 0
    update.message.reply_text(
        f"<b>Ваш счёт:</b>\n"
        f"{score} из {total} ({percent:.0f}%)",
        parse_mode="HTML",
        reply_markup=get_quiz_keyboard_after_answer(),
    )
    return States.AFTER_ANSWER


def block_new_question_during_active(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Сначала закончи текущий вопрос!",
        reply_markup=get_quiz_keyboard(),
    )
    return States.QUESTION_ACTIVE


def main() -> None:
    from dotenv import load_dotenv
    import redis

    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не найден в .env")

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv("REDIS_PASSWORD") or None
    redis_db = int(os.getenv("REDIS_DB", 0))

    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        password=redis_password,
        db=redis_db,
        decode_responses=True,
    )

    with open("questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    updater = Updater(bot_token, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.IDLE: [
                MessageHandler(Filters.regex("^Новый вопрос$"), lambda u, c: handle_new_question_request(u, c, questions, redis_client)),
            ],
            States.QUESTION_ACTIVE: [
                MessageHandler(Filters.regex("^Сдаться$"), lambda u, c: surrender(u, c, redis_client)),
                MessageHandler(Filters.regex("^Новый вопрос$"), block_new_question_during_active),
                MessageHandler(Filters.text & ~Filters.command, lambda u, c: handle_solution_attempt(u, c, redis_client)),
            ],
            States.AFTER_ANSWER: [
                MessageHandler(Filters.regex("^Новый вопрос$"), lambda u, c: handle_new_question_request(u, c, questions, redis_client)),
                MessageHandler(Filters.regex("^Мой счёт$"), lambda u, c: my_score(u, c, redis_client)),
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