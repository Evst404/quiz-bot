import json
import os
import random
import re
from typing import Any

import redis
from dotenv import load_dotenv
from vk_api import VkApi
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType


def get_vk_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Новый вопрос", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Сдаться", color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    kb.add_button("Мой счёт", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def normalize_answer(text: str) -> str:
    text = re.split(r"[.(]", text)[0]
    text = re.sub(r'[.,!?;:"\'()–—-]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def send_message(vk_api: Any, user_id: int, text: str, keyboard: str = None) -> None:
    vk_api.messages.send(
        user_id=user_id,
        message=text,
        random_id=random.randint(1, 1000),
        keyboard=keyboard,
    )


def handle_vk_message(event: Any, vk_api: Any, questions: list, r: Any) -> None:
    user_id = str(event.user_id)
    text = event.text
    kb = get_vk_keyboard()

    if text == "Новый вопрос":
        if r.get(f"user:{user_id}:current_question"):
            send_message(vk_api, user_id, "Сначала закончи текущий вопрос!", kb)
        else:
            q = random.choice(questions)
            r.set(f"user:{user_id}:current_question", json.dumps(q))
            r.set(f"user:{user_id}:attempts", 0)
            send_message(vk_api, user_id, f"Вопрос:\n\n{q['question']}", kb)
        return

    if text == "Сдаться":
        cur = r.get(f"user:{user_id}:current_question")
        if cur:
            q = json.loads(cur)
            send_message(vk_api, user_id, f"Вы сдались!\n\nПравильный ответ: {q['answer']}", kb)
            r.delete(f"user:{user_id}:current_question")
            r.delete(f"user:{user_id}:attempts")
        else:
            send_message(vk_api, user_id, "Вы ещё не начали викторину!", kb)
        return

    if text == "Мой счёт":
        score = int(r.get(f"user:{user_id}:score") or 0)
        total = int(r.get(f"user:{user_id}:total") or 0)
        percent = (score / total * 100) if total > 0 else 0
        send_message(vk_api, user_id, f"Ваш счёт: {score} из {total} ({percent:.0f}%)", kb)
        return

    cur = r.get(f"user:{user_id}:current_question")
    if cur:
        q = json.loads(cur)
        user_norm = normalize_answer(text)
        correct_norm = normalize_answer(q["answer"])

        attempts = int(r.get(f"user:{user_id}:attempts") or 0) + 1
        r.set(f"user:{user_id}:attempts", attempts)

        if user_norm == correct_norm:
            send_message(vk_api, user_id, "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос».", kb)
            score = int(r.get(f"user:{user_id}:score") or 0) + 1
            r.set(f"user:{user_id}:score", score)
            r.delete(f"user:{user_id}:current_question")
            r.delete(f"user:{user_id}:attempts")
        else:
            if attempts >= 2:
                hint = q["answer"].split(".")[0].split("(")[0].strip()
                send_message(vk_api, user_id, f"Неправильно… Попробуешь ещё раз?\n\nПодсказка: {hint[:15]}...", kb)
            else:
                send_message(vk_api, user_id, "Неправильно… Попробуешь ещё раз?", kb)

        total = int(r.get(f"user:{user_id}:total") or 0) + 1
        r.set(f"user:{user_id}:total", total)
        return

    if text.lower() in ["привет", "старт", "start"]:
        send_message(vk_api, user_id, "Привет! Я бот для викторины!\nНажми «Новый вопрос», чтобы начать!", kb)
        return

    send_message(vk_api, user_id, text, kb)


def main() -> None:
    load_dotenv()

    VK_TOKEN = os.getenv("VK_TOKEN")
    if not VK_TOKEN:
        raise RuntimeError("VK_TOKEN не найден в .env")

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

    session = VkApi(token=VK_TOKEN)
    vk_api = session.get_api()
    longpoll = VkLongPoll(session)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            handle_vk_message(event, vk_api, QUESTIONS, r)


if __name__ == "__main__":
    main()