from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from dotenv import load_dotenv
import os


load_dotenv()


TOKEN = os.getenv("BOT_TOKEN")

def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Здравствуйте")

def echo(update: Update, _: CallbackContext) -> None:
    update.message.reply_text(update.message.text)

def main():
    if not TOKEN:
        print("ОШИБКА: BOT_TOKEN не найден в .env")
        return

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    print("Бот запущен...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()