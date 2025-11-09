import json
import os
import re
from typing import List


def clean_text(text: str) -> str:
    text = re.sub(r'[.,!?;:"\'()–—-]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_file(filepath: str, questions: List[dict]) -> None:
    try:
        with open(filepath, "r", encoding="koi8-r") as f:
            content = f.read()

        blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
        current_question = None
        current_answer = None

        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            first_line = lines[0]

            if first_line.startswith("Вопрос"):
                if current_question and current_answer:
                    questions.append(
                        {
                            "question": clean_text(current_question),
                            "answer": clean_text(current_answer),
                        }
                    )
                q_text = " ".join(lines[1:]) if len(lines) > 1 else ""
                current_question = q_text
                current_answer = None

            elif first_line.startswith("Ответ"):
                if current_question:
                    raw_answer = " ".join(lines[1:]) if len(lines) > 1 else ""
                    current_answer = raw_answer

        if current_question and current_answer:
            questions.append(
                {
                    "question": clean_text(current_question),
                    "answer": clean_text(current_answer),
                }
            )

    except Exception as e:
        print(f"Ошибка в {filepath}: {e}")


def main() -> None:
    QUESTIONS_DIR = "quiz-questions"
    OUTPUT_FILE = "questions.json"
    LIMIT = 1000

    if not os.path.exists(QUESTIONS_DIR):
        print(f"ПАПКА НЕ НАЙДЕНА: {QUESTIONS_DIR}")
        return

    files = [
        f
        for f in os.listdir(QUESTIONS_DIR)
        if os.path.isfile(os.path.join(QUESTIONS_DIR, f))
    ]
    print(f"Найдено файлов: {len(files)}")

    questions: List[dict] = []
    for i, filename in enumerate(sorted(files)):
        filepath = os.path.join(QUESTIONS_DIR, filename)
        parse_file(filepath, questions)
        if (i + 1) % 500 == 0:
            print(f"Обработано: {i + 1} файлов...")

    if len(questions) > LIMIT:
        print(f"\nОграничиваем до {LIMIT} вопросов")
        questions = questions[:LIMIT]

    print(f"\nГотово! Вопросов: {len(questions)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f"Сохранено в: {OUTPUT_FILE}")

    print("\nПервые 3 вопроса:")
    for q in questions[:3]:
        print(f"Q: {q['question']}")
        print(f"A: {q['answer']}\n")


if __name__ == "__main__":
    main()