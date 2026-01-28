# line-task-bot
from flask import Flask, request, abort import os  app = Flask(__name__)  @app.route("/") def home():     return "Bot is running!"  @app.route("/webhook", methods=["POST"]) def webhook():     body = request.json     print(body)     return "OK", 200  if __name__ == "__main__":     app.run()
