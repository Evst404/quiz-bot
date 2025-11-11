# Quiz Bot — Викторина в Telegram и VK

## Описание проекта

**Quiz Bot** — это **интерактивная викторина** по базе «Что? Где? Когда?», работающая **одновременно в Telegram и ВКонтакте**.

**Telegram**: [@devman_quizzz_bot](https://t.me/devman_quizzz_bot)  
**VK**: [vk.com/club225320139](https://vk.com/club225320139)

---

## Переменные окружения (`.env`)



| Переменная         | Описание                          | Пример                                  |
|--------------------|-----------------------------------|-----------------------------------------|
| `BOT_TOKEN`        | Токен Telegram-бота               | `123456:ABC-...`                        |
| `VK_TOKEN`         | Токен группы VK                   | `vk1.a.-NWDy_...`                       |
| `REDIS_HOST`       | Хост Redis                        | `redis-16856.c74.us-east-1-4.ec2.redns.redis-cloud.com` |
| `REDIS_PORT`       | Порт Redis                        | `16856`                                 |
| `REDIS_PASSWORD`   | Пароль Redis                      | `2fCICEPqkOya...`                       |
| `REDIS_DB`         | Номер базы Redis (0–15)           | `0`                                     |

> **Важно:** Используются префиксы `tg-` и `vk-` в Redis для разделения пользователей.

---


## Установка и запуск
```
1. Клонировать репозиторий
git clone git@github.com:Evst404/quiz-bot.git
cd quiz-bot

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать .env
cp .env.example .env
# Отредактируйте .env — вставьте свои токены

# 5. Сгенерировать questions.json
python generate_questions.py --input-dir quiz-questions --limit 1000

# 6. Запустить ботов
python bot.py     # Telegram
python vk-bot.py  # VK

```

# Деплой
```
Сервер: DigitalOcean Droplet (Ubuntu 22.04)
IP: 178.128.196.169
Боты запущены через systemd
Redis: Redis Cloud (30 МБ)
```


# Технологии

1. Python 3.10
2. python-telegram-bot==13.15
3. vk_api
4. redis-py
5. python-dotenv
6. systemd
7. DigitalOcean + Redis Cloud

---

Автор
Evst404
GitHub: @Evst404



