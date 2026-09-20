import os
import telebot
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing.")

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    return "Group Management Bot is running!"


@app.route("/api/webhook", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")

    update = telebot.types.Update.de_json(
        json_string
    )

    bot.process_new_updates([update])

    return "OK", 200
