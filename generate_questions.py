import argparse
import json
import os
import re
from typing import List


INPUT_DIR_DEFAULT = "quiz-questions"
OUTPUT_FILE_DEFAULT = "questions.json"
MAX_QUESTIONS_DEFAULT = 1000


def clean_text(text: str) -> str:
    text = re.sub(r'[.,!?;:"\'()–—-]', "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_file(filepath: str, questions: List[dict]) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate questions.json from quiz-questions")
    parser.add_argument("--input-dir", default=INPUT_DIR_DEFAULT)
    parser.add_argument("--output-file", default=OUTPUT_FILE_DEFAULT)
    parser.add_argument("--limit", type=int, default=MAX_QUESTIONS_DEFAULT)
    args = parser.parse_args()

    input_dir = args.input_dir
    output_file = args.output_file
    max_questions = args.limit

    if not os.path.exists(input_dir):
        print(f"ПАПКА НЕ НАЙДЕНА: {input_dir}")
        return

    files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]

    questions: List[dict] = []
    for filename in sorted(files):
        filepath = os.path.join(input_dir, filename)
        parse_file(filepath, questions)

    if len(questions) > max_questions:
        questions = questions[:max_questions]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()