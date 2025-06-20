from flask import Flask
from flask import request
from threading import Thread
import time
import requests

app = Flask('')

@app.route('/')
def home():
  return "Сервер включен"

def run():
  app.run(host="0.0.0.0", port=80)

def keep_alive():
  t = Thread(target=run)
  t.start()