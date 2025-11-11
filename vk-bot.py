import json
import os
import random
import re
from typing import Any

from vk_api import VkApi
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType


def get_quiz_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button("Новый вопрос", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Сдаться", color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    kb.add_button("Мой счёт", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def get_quiz_keyboard_after_answer():
    kb = VkKeyboard(one_time=False)
    kb.add_button("Новый вопрос", color=VkKeyboardColor.PRIMARY)
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
        random_id=random.randint(1, 1000000),
        keyboard=keyboard,
    )


def handle_new_question(vk_api: Any, user_id: str, kb: str, questions, redis_client) -> None:
    question = random.choice(questions)
    redis_client.set(f"vk-{user_id}:current_question", json.dumps(question))
    redis_client.set(f"vk-{user_id}:attempts", 0)
    send_message(vk_api, user_id, f"Вопрос:\n\n{question['question']}", kb)


def handle_surrender(vk_api: Any, user_id: str, kb: str, redis_client) -> None:
    current_question_json = redis_client.get(f"vk-{user_id}:current_question")
    if current_question_json:
        question = json.loads(current_question_json)
        send_message(vk_api, user_id, f"Вы сдались!\n\nПравильный ответ: {question['answer']}", kb)
        redis_client.delete(f"vk-{user_id}:current_question")
        redis_client.delete(f"vk-{user_id}:attempts")
    else:
        send_message(vk_api, user_id, "Вы ещё не начали викторину!", kb)


def handle_my_score(vk_api: Any, user_id: str, kb: str, redis_client) -> None:
    score = int(redis_client.get(f"vk-{user_id}:score") or 0)
    total = int(redis_client.get(f"vk-{user_id}:total") or 0)
    percent = (score / total * 100) if total > 0 else 0
    send_message(vk_api, user_id, f"Ваш счёт: {score} из {total} ({percent:.0f}%)", kb)


def handle_answer(vk_api: Any, user_id: str, text: str, kb: str, redis_client) -> None:
    current_question_json = redis_client.get(f"vk-{user_id}:current_question")
    if not current_question_json:
        return

    question = json.loads(current_question_json)
    user_answer_normalized = normalize_answer(text)
    correct_answer_normalized = normalize_answer(question["answer"])

    attempts = int(redis_client.get(f"vk-{user_id}:attempts") or 0) + 1
    redis_client.set(f"vk-{user_id}:attempts", attempts)

    if user_answer_normalized == correct_answer_normalized:
        send_message(vk_api, user_id, "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос».", kb)
        score = int(redis_client.get(f"vk-{user_id}:score") or 0) + 1
        redis_client.set(f"vk-{user_id}:score", score)
        redis_client.delete(f"vk-{user_id}:current_question")
        redis_client.delete(f"vk-{user_id}:attempts")
    else:
        if attempts >= 2:
            hint = question["answer"].split(".")[0].split("(")[0].strip()
            send_message(vk_api, user_id, f"Неправильно… Попробуешь ещё раз?\n\nПодсказка: {hint[:15]}...", kb)
        else:
            send_message(vk_api, user_id, "Неправильно… Попробуешь ещё раз?", kb)

    total = int(redis_client.get(f"vk-{user_id}:total") or 0) + 1
    redis_client.set(f"vk-{user_id}:total", total)


def handle_vk_message(event: Any, vk_api: Any, questions, redis_client) -> None:
    user_id = str(event.user_id)
    text = event.text
    kb_active = get_quiz_keyboard()
    kb_after = get_quiz_keyboard_after_answer()

    current_question = redis_client.get(f"vk-{user_id}:current_question")

    if text == "Новый вопрос":
        if current_question:
            send_message(vk_api, user_id, "Сначала закончи текущий вопрос!", kb_active)
        else:
            handle_new_question(vk_api, user_id, kb_active, questions, redis_client)
        return

    if text == "Сдаться":
        if current_question:
            handle_surrender(vk_api, user_id, kb_after, redis_client)
        else:
            send_message(vk_api, user_id, "Вы ещё не начали викторину!", kb_active)
        return

    if text == "Мой счёт":
        if current_question:
            send_message(vk_api, user_id, "Сначала закончи текущий вопрос!", kb_active)
        else:
            handle_my_score(vk_api, user_id, kb_after, redis_client)
        return

    if current_question:
        handle_answer(vk_api, user_id, text, kb_active, redis_client)
        return

    if text.lower() in ["привет", "старт", "start"]:
        send_message(vk_api, user_id, "Привет! Я бот для викторины!\nНажми «Новый вопрос», чтобы начать!", kb_active)
        return

    send_message(vk_api, user_id, text, kb_active)


def main() -> None:
    from dotenv import load_dotenv
    import redis

    load_dotenv()

    vk_token = os.getenv("VK_TOKEN")
    if not vk_token:
        raise RuntimeError("VK_TOKEN не найден в .env")

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

    session = VkApi(token=vk_token)
    vk_api = session.get_api()
    longpoll = VkLongPoll(session)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            handle_vk_message(event, vk_api, questions, redis_client)


if __name__ == "__main__":
    main()