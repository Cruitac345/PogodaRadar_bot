import os
from threading import Condition, local
from telebot.types import KeyboardButton, Message, ReplyKeyboardMarkup
from telebot import types
from background import keep_alive #импорт функции для поддержки работоспособности
import pip
from telegram.constants import ParseMode
from PIL import Image
from io import BytesIO
import requests
from bs4 import BeautifulSoup
from telegram.ext import Updater, CommandHandler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from datetime import datetime, timedelta
pip.main(['install', 'pytelegrambotapi'])
import pytaf
import telebot, apihelper
from telebot import types
from telebot.types import InputMediaPhoto
import telegram
import python-template
import time
import locale
import pytz
from urllib import request
import concurrent.futures
import pandas as pd
import re
import json
import csv
import logging
import random

bot = telebot.TeleBot('7308011756:AAEj5V6c2lC_JlxUNJLW5e1Feji_VpgB7GY', skip_pending=True)
ADMIN_ID = 1117968372  # Замените на ваш ID
weather_url = 'http://api.weatherapi.com/v1'
api_key = 'cacfd66797d643b8bf6193226220101'
lang = 'ru'

# Глобальные переменные для хранения состояния игры
user_guess_temp_state = {}

# Имя файла, где будут храниться данные о городах
CITIES_FILE = 'cities.csv'

# Функция для сохранения города в CSV
def save_city(user_id, city_name):
    user_id = str(user_id)
    city_name = city_name.strip()

    # Если файл не существует, создаем его
    if not os.path.exists(CITIES_FILE):
        with open(CITIES_FILE, mode='w', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['user_id', 'city'])

    # Читаем существующие данные
    data = {}
    with open(CITIES_FILE, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) == 2:  # Проверяем, что строка корректна
                data[row[0]] = row[1]

    # Обновляем или добавляем значение для текущего пользователя
    data[user_id] = city_name

    # Перезаписываем файл с обновленными данными
    with open(CITIES_FILE, mode='w', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['user_id', 'city'])  # Заголовок
        for uid, city in data.items():
            writer.writerow([uid, city])

# Функция для загрузки города пользователя из CSV
def load_city(user_id):
    user_id = str(user_id)
    if not os.path.exists(CITIES_FILE):
        return None
    with open(CITIES_FILE, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) == 2 and row[0] == user_id:
                return row[1]
    return None


# Функция для записи статистики
def log_user_activity(user_id, username, action):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = str(user_id)  # Преобразуем user_id в строку для консистентности
    action = action.strip()  # Убираем лишние пробелы для корректного сравнения

    # Проверяем, существует ли файл
    file_exists = os.path.exists('user_statistics.csv')

    # Проверяем, есть ли пользователь с таким действием в файле
    if file_exists:
        with open('user_statistics.csv', mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None)  # Пропускаем заголовок
            for row in reader:
                if len(row) >= 3 and row[0] == user_id and row[2] == action:
                    # Если пользователь с таким действием уже записан, выходим из функции
                    return

    # Если пользователь с таким действием еще не записан, добавляем запись
    with open('user_statistics.csv', mode='a', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['User ID', 'Username', 'Action', 'Timestamp'])  # Заголовки столбцов
        writer.writerow([user_id, username, action, current_time])


# Хранилище для отслеживания запросов пользователей (антифлуд)
user_requests = {}  # Формат: {user_id: {'last_request_time': float, 'request_count': int}}
FLOOD_LIMIT = 5      # Максимальное количество запросов за интервал времени
FLOOD_INTERVAL = 60  # Интервал времени в секундах (1 минута)

# Антифлуд-функция
# Хранилище для отслеживания запросов пользователей (антифлуд)
user_requests = {}  # Формат: {user_id: {'last_request_time': float, 'request_count': int, 'is_blocked': bool, 'block_until': float}}
FLOOD_LIMIT = 12     # Максимальное количество запросов за интервал времени
FLOOD_INTERVAL = 60  # Интервал времени в секундах (1 минута)
BLOCK_TIME = 60       # Время блокировки в секундах (1 минута)

# Антифлуд-функция
def is_flooding(user_id):
    current_time = time.time()

    # Если пользователь ещё не отслеживается
    if user_id not in user_requests:
        user_requests[user_id] = {
            'last_request_time': current_time,
            'request_count': 1,
            'is_blocked': False,
            'block_until': 0
        }
        return False

    user_data = user_requests[user_id]

    # Если пользователь заблокирован, проверить, истёк ли срок блокировки
    if user_data['is_blocked']:
        if current_time >= user_data['block_until']:
            # Снимаем блокировку
            user_data['is_blocked'] = False
            user_data['request_count'] = 1
            user_data['last_request_time'] = current_time
            return False
        else:
            # Пользователь всё ещё заблокирован
            return True

    # Проверить, сколько времени прошло с последнего запроса
    time_since_last_request = current_time - user_data['last_request_time']

    if time_since_last_request > FLOOD_INTERVAL:
        # Если прошло больше интервала времени, сбросить счётчик
        user_data['request_count'] = 1
        user_data['last_request_time'] = current_time
        return False

    # Увеличиваем счётчик запросов
    user_data['request_count'] += 1
    user_data['last_request_time'] = current_time

    # Проверяем, превышен ли лимит запросов
    if user_data['request_count'] > FLOOD_LIMIT:
        # Заблокировать пользователя на BLOCK_TIME
        user_data['is_blocked'] = True
        user_data['block_until'] = current_time + BLOCK_TIME
        return True

def load_city_data(file_path):
    city_data = []
    with open(file_path, mode='r', encoding='utf-8', newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            city_data.append({'eng_name': row[0].strip(), 'rus_name': row[1].strip(), 'url': row[2].strip()})
    return city_data
  
city_data = load_city_data('city_data.csv')

@bot.message_handler(commands=['start'])
def get_text_message(message):
  # Логируем активность
  log_user_activity(message.from_user.id, message.from_user.username, '/start')

  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn1 = KeyboardButton('🚨Помощь')
  btn2 = KeyboardButton('🗺️Радар')
  btn3 = KeyboardButton('⛅Погода сейчас')
  btn4 = KeyboardButton('📆Погода на 3 дня')
  btn5 = KeyboardButton('🌫️Качество воздуха')
  btn6 = KeyboardButton('🎁Поддержать')
  btn7 = KeyboardButton('📢Поделиться ботом')
  btn8 = KeyboardButton('✈️Погода в аэропортах')
  btn9 = KeyboardButton('📍Определить локацию')
  btn10 = KeyboardButton('📊Метеограммы ГМЦ')
  btn11 = KeyboardButton('✏️Изменить город')
  markup.row(btn1, btn2)
  markup.row(btn8, btn5)
  markup.row(btn3, btn4)
  markup.row(btn6, btn7)
  markup.row(btn10)
  markup.row(btn9)
  markup.row(btn11)

  bot.send_message(message.from_user.id, 'Привет! Я - бот погоды PogodaRadar. Спроси меня о погоде в своем городе или любом другом месте, которое тебя интересует!😊🌦️', reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
      user_id = message.from_user.id
      if is_flooding(user_id):
        bot.send_message(user_id, "⚠️ Вы заблокированы на 1 минуту из-за частых запросов.")
        return
      if message.text == '🚨Помощь' or message.text == '/help':
        get_help(message)
      elif message.text == '🗺️Радар' or message.text == '/radarmap':
        get_radar_map(message)
      elif message.text == '⛅Погода сейчас' or message.text == '/nowweather':
        now_weather(message)
      elif message.text == '📆Погода на 3 дня' or message.text == '/forecastweather':
        forecast_weather(message)
      elif message.text == '✈️Погода в аэропортах' or message.text == '/weatherairports':
        get_airport_weather(message)
      elif message.text == '🌫️Качество воздуха' or message.text == '/aqi':
        get_city_aqi(message)
      elif message.text == '🎁Поддержать' or message.text == '/donate':
        get_donate(message)
      elif message.text == '📢Поделиться ботом' or message.text == '/share':
        get_share(message)
      elif message.text == '📊Метеограммы ГМЦ' or message.text == '/meteograms':
        start_meteogram_request(message)
      elif message.text == '📍Определить локацию':
        get_location(message)
      elif message.text == '✏️Изменить город' or message.text == '/setcity':
        set_city(message)
      elif message.text == '/precipitationmap':
        get_precipitation_map(message)
      elif message.text == '/alerts':
        alerts_weather(message)
      elif message.text == '/anomaltempmap':
        get_anomal_temp_map(message)
      elif message.text == '/weatherwebsites':
        websites_weather(message)
      elif message.text == '/tempwatermap':
        get_tempwater_map(message)
      elif message.text == '/verticaltemplayer':
        get_vertical_temp(message)
      elif message.text == '/firehazard_map':
        get_firehazard_map(message)
      elif message.text == '/extrainfo':
        send_extrainfo(message)
      elif message.text == '/stations':
        send_weather_stations(message)
      elif message.text == '/get_meteoweb':
        get_map_command(message)
      elif message.text == '/support':
        get_support(message)
      elif message.text == '/stats':
        show_statistics(message)
      elif message.text == '/guess_temp':
        start_guess_temp(message)
# echo-функция, которая присылает сообщение от бота

@bot.message_handler(commands=['guess_temp'])
def handle_guess_temp_command(message):
    """
    Обрабатывает команду /guess_temp и запускает игру.
    """
    start_guess_temp(message)

def start_guess_temp(message):
    """
    Начинает игру "Угадай температуру".
    """
    user_id = message.from_user.id
    user_guess_temp_state[user_id] = {"target_temp": random.randint(-30, 40), "attempts": 0, "max_attempts": 5}

    bot.send_message(user_id, "🌡️ Я загадал температуру от -30°C до 40°C. Попробуй угадать её за 5 попыток!")
    bot.send_message(user_id, "❓ Введи свою догадку:")
    bot.register_next_step_handler(message, process_guess_temp)

def process_guess_temp(message):
    """
    Обрабатывает попытку угадать температуру.
    """
    user_id = message.from_user.id
    if user_id not in user_guess_temp_state:
        bot.send_message(user_id, "Игра не начата. Введите /guess_temp, чтобы начать.")
        return

    target_temp = user_guess_temp_state[user_id]["target_temp"]
    attempts = user_guess_temp_state[user_id]["attempts"]
    max_attempts = user_guess_temp_state[user_id]["max_attempts"]

    try:
        guess = int(message.text)
        attempts += 1

        if guess == target_temp:
            bot.send_message(user_id, f"🎉 Поздравляю! Ты угадал за {attempts} попыток. Это действительно {target_temp}°C!")
            del user_guess_temp_state[user_id]  # Очищаем состояние
        else:
            if attempts >= max_attempts:
                bot.send_message(user_id, f"😔 К сожалению, ты исчерпал все попытки. Загаданная температура была {target_temp}°C.")
                del user_guess_temp_state[user_id]  # Очищаем состояние
            else:
                difference = abs(target_temp - guess)
                hint = ""

                if difference > 20:
                    hint = "❄️ Очень холодно! Попробуй ближе к середине диапазона."
                elif difference > 10:
                    hint = "🌬️ Холодно, но уже теплее!"
                elif difference > 5:
                    hint = "🌤️ Тепло, но можно ещё лучше!"
                else:
                    hint = "🔥 Горячо! Ты почти угадал!"

                bot.send_message(user_id, f"{hint}\n❓ Попытка {attempts} из {max_attempts}. Введи следующую догадку:")
                user_guess_temp_state[user_id]["attempts"] = attempts
                bot.register_next_step_handler(message, process_guess_temp)
    except ValueError:
        bot.send_message(user_id, "⚠️ Пожалуйста, введите целое число.")
        bot.register_next_step_handler(message, process_guess_temp)

# Команда /setcity для установки города
@bot.message_handler(commands=['setcity'])
def set_city(message):
    msg = bot.send_message(message.from_user.id, 'Введите название города, который вы хотите установить:')
    bot.register_next_step_handler(msg, save_user_city)


def save_user_city(message):
    city = message.text
    save_city(message.from_user.id, city)
    bot.send_message(message.from_user.id, f'Город "{city}" успешно сохранен!')

# Обработчик команды /stats
@bot.message_handler(commands=['stats'])
def show_statistics(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "У вас нет доступа к этой команде.")
        return

    try:
        with open('user_statistics.csv', mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            stats = list(reader)
            print(f"Прочитано строк из файла: {len(stats)}")  # Отладочное сообщение

        if not stats or len(stats) == 1:  # Если файл пуст или содержит только заголовок
            bot.reply_to(message, "Статистика пока отсутствует.")
            return

        # Формируем сообщение со статистикой
        stats_message = "📊 Статистика пользования ботом:\n\n"
        for row in stats[1:]:  # Пропускаем заголовок
            if len(row) >= 4:  # Проверяем, что строка содержит все необходимые данные
                stats_message += f"👤 Пользователь: {row[1]} (ID: {row[0]})\n"
                stats_message += f"🕒 Время: {row[3]}\n"
                stats_message += f"📝 Действие: {row[2]}\n"
                stats_message += "────────────────────\n"
            else:
                print(f"Некорректная строка в файле: {row}")  # Отладочное сообщение

        bot.reply_to(message, stats_message)
    except FileNotFoundError:
        bot.reply_to(message, "Файл статистики не найден.")
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")  # Отладочное сообщение
        bot.reply_to(message, "Произошла ошибка при чтении файла статистики.")

# Обработчик всех текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    # Логируем активность
    log_user_activity(message.from_user.id, message.from_user.username, f"Сообщение: {message.text}")

    # Обработка текстовых сообщений
    bot.reply_to(message, "Извините, я пока не понимаю этот запрос. Попробуйте использовать команды из меню.")


def get_location(message):
  keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
  button_geo = types.KeyboardButton(text="Отправить местоположение", request_location=True)
  keyboard.add(button_geo)
  bot.send_message(message.chat.id, "Нажмите кнопку, чтобы отправить свое местоположение:", reply_markup=keyboard)

@bot.message_handler(content_types=['location'])
def handle_location(message):
    lat = message.location.latitude
    lon = message.location.longitude
    geocoder_params = {'q': f'{lat},{lon}', 'key': api_key}
    try:
        geocoder_response = requests.get(f'{weather_url}/search.json', params=geocoder_params).json()
        if geocoder_response and 'name' in geocoder_response[0]:
            city_name = geocoder_response[0]['name']
            save_city(message.from_user.id, city_name)  # Сохраняем город в CSV
            now_weather_by_coords(message, city_name)

            # Убираем клавиатуру с кнопкой "Отправить местоположение"
            remove_keyboard = types.ReplyKeyboardRemove()
            bot.send_message(message.chat.id, "Местоположение определено. Спасибо!", reply_markup=remove_keyboard)
            
        else:
            bot.send_message(message.chat.id, "Не удалось определить город по координатам. Пожалуйста, введите название города вручную.")
            bot.register_next_step_handler(message, now_weather)
    except (IndexError, KeyError, requests.exceptions.RequestException) as e:
        print(f"Ошибка при определении местоположения: {e}")
        bot.send_message(message.chat.id, "Ошибка определения местоположения. Пожалуйста, введите название города вручную.")
        bot.register_next_step_handler(message, now_weather)

def now_weather_by_coords(message, city_name):
  parameters = {'key': api_key, 'q': city_name, 'lang': 'ru'}
  try:
      # Получаем текущие данные о погоде
      response = requests.get(f'{weather_url}/current.json', params=parameters).json()
      astronomy_parameters = {'key': api_key, 'q': city_name, 'lang': 'ru'}
      astronomy_response = requests.get(f'{weather_url}/astronomy.json',               params=astronomy_parameters).json()

      # Обрабатываем данные
      data = response
      astronomy_data = astronomy_response

      location = data['location']['name'] + ', ' + data['location']['country']
      local_time = datetime.strptime(data['location']['localtime'], '%Y-%m-%d %H:%M').strftime('%d %B %Y %H:%M')
      update_current = datetime.strptime(data['current']['last_updated'], '%Y-%m-%d %H:%M').strftime('%d %B %Y %H:%M')
      months = {
          'January': 'Января',
          'February': 'Февраля',
          'March': 'Марта',
          'April': 'Апреля',
          'May': 'Мая',
          'June': 'Июня',
          'July': 'Июля',
          'August': 'Августа',
          'September': 'Сентября',
          'October': 'Октября',
          'November': 'Ноября',
          'December': 'Декабря'
      }
      local_time = ' '.join([months.get(month, month) for month in local_time.split()])
      update_current = ' '.join([months.get(month, month) for month in update_current.split()])

      condition_code = str(data['current']['condition']['code'])
      condition = data['current']['condition']['text']
      temp_c = data['current']['temp_c']
      feelslike_c = data['current']['feelslike_c']
      wind = data['current']['wind_kph']
      wind_dir = data['current']['wind_dir']
      humidity = data['current']['humidity']
      clouds = data['current']['cloud']
      pressure = int(data['current']['pressure_mb'])
      uv_index = int(data['current']['uv'])
      vis_km = data['current']['vis_km']
      sunrise = astronomy_data['astronomy']['astro']['sunrise'].replace('AM', 'Утра')
      sunset = astronomy_data['astronomy']['astro']['sunset'].replace('PM', 'Вечера')
      weather_icons = {
            '1000': '☀️',  # Sunny / Clear
            '1003': '🌤️',  # Partly cloudy
            '1006': '☁️',  # Cloudy
            '1009': '☁️',  # Overcast
            '1030': '🌫️',  # Mist
            '1063': '🌦️',  # Patchy rain possible
            '1066': '❄️',  # Patchy snow possible
            '1069': '🌨️',  # Patchy sleet possible
            '1072': '☔',  # Patchy freezing drizzle possible
            '1087': '🌩️',  # Thundery outbreaks possible
            '1114': '❄️🌬️',  # Blowing snow
            '1117': '❄️🌬️',  # Blizzard
            '1135': '🌫️',  # Fog
            '1147': '🌫️🥶',  # Freezing fog
            '1150': '🌧️',  # Patchy light drizzle
            '1153': '🌧️',  # Light drizzle
            '1168': '🌧️',  # Freezing drizzle
            '1171': '🌧️',  # Heavy freezing drizzle
            '1180': '🌧️',  # Patchy light rain
            '1183': '🌧️',  # Light rain
            '1186': '🌧️',  # Moderate rain at times
            '1189': '🌧️',  # Moderate rain
            '1192': '🌧️',  # Heavy rain at times
            '1195': '🌧️',  # Heavy rain
            '1198': '🌧️❄️',  # Light freezing rain
            '1201': '🌧️❄️',  # Moderate or heavy freezing rain
            '1204': '🌨️',  # Light sleet
            '1207': '🌨️',  # Moderate or heavy sleet
            '1210': '❄️',  # Patchy light snow
            '1213': '❄️',  # Light snow
            '1216': '❄️',  # Patchy moderate snow
            '1219': '❄️',  # Moderate snow
            '1222': '❄️',  # Patchy heavy snow
            '1225': '❄️',  # Heavy snow
            '1237': '🌨️',  # Ice pellets
            '1240': '🌧️',  # Light rain shower
            '1243': '🌧️',  # Moderate or heavy rain shower
            '1246': '🌧️',  # Torrential rain shower
            '1249': '🌨️',  # Light sleet showers
            '1252': '🌨️',  # Moderate or heavy sleet showers
            '1255': '❄️',  # Light snow showers
            '1258': '❄️',  # Moderate or heavy snow showers
            '1261': '🌨️',  # Light showers of ice pellets
            '1264': '🌨️',  # Moderate or heavy showers of ice pellets
            '1273': '⛈️',  # Patchy light rain with thunder
            '1276': '⛈️',  # Moderate or heavy rain with thunder
            '1279': '⛈️❄️',  # Patchy light snow with thunder
            '1282': '⛈️❄️',  # Moderate or heavy snow with thunder
        }
      emoji = weather_icons.get(condition_code, '✖️')
      wind_mps = convert_to_mps(wind)
      wind_dir_text = get_wind_direction(wind_dir)

      clothing_recommendations = ''

      # Temperature-based recommendations
      if temp_c < -10:
          clothing_recommendations += '❄️ Сильный мороз: Наденьте термобелье, утепленные штаны, пуховик или шубу, шапку-ушанку, шарф, теплые перчатки и зимнюю обувь с мехом.\n'
      elif -10 <= temp_c < 0:
          clothing_recommendations += '❄️ Мороз: Наденьте теплое пальто или пуховик, шапку, шарф, перчатки и утепленную обувь.\n'
      elif 0 <= temp_c < 10:
          clothing_recommendations += '🧥 Прохладно: Наденьте теплую куртку, свитер, джинсы или утепленные брюки, легкую шапку или капюшон.\n'
      elif 10 <= temp_c < 15:
          clothing_recommendations += '🧥 Легкая прохлада: Наденьте ветровку, джинсовку или толстовку, брюки или джинсы.\n'
      elif 15 <= temp_c < 20:
          clothing_recommendations += '👕 Комфортно: Наденьте легкую куртку или кардиган, футболку или рубашку, джинсы или брюки.\n'
      elif 20 <= temp_c < 25:
          clothing_recommendations += '👕 Тепло: Наденьте футболку, шорты или легкие брюки, можно взять с собой легкую кофту на случай ветра.\n'
      else:
          clothing_recommendations += '🔥 Жарко: Наденьте легкую одежду из дышащих тканей, шорты, майку или сарафан. Не забудьте головной убор и солнцезащитные очки.\n'

      # Wind-based recommendations
      if wind >= 40:
        clothing_recommendations += '🌬️ Сильный ветер: Рекомендуем надеть ветровку, плотную куртку и плотные брюки.\n'
      elif wind >= 20:
        clothing_recommendations += '💨 Умеренный ветер: Наденьте легкую блузку, рубашку или футболку и брюки.\n'

      # Humidity-based recommendations
      if humidity >= 90:
          clothing_recommendations += '🌧️ Очень высокая влажность: Наденьте водонепроницаемую куртку, непромокаемые штаны и резиновые сапоги. Возьмите зонт.\n'
      elif humidity >= 80:
          clothing_recommendations += '🌧️ Высокая влажность: Наденьте водонепроницаемую куртку и непромокаемую обувь.\n'
      elif humidity >= 60:
          clothing_recommendations += '💦 Повышенная влажность: Наденьте дышащую одежду и обувь, которая не промокает.\n'

      # Pressure-based recommendations
      if pressure <= 970:
          clothing_recommendations += '🌪️ Очень низкое давление: Наденьте непромокаемую одежду, возьмите зонт и дополнительный слой одежды на случай резких изменений погоды.\n'
      elif pressure <= 990:
          clothing_recommendations += '🌫️ Низкое давление: Возьмите с собой легкую куртку или свитер, чтобы утеплиться в случае похолодания.\n'
      elif pressure >= 1030:
          clothing_recommendations += '☀️ Высокое давление: Наденьте легкую одежду, так как погода, скорее всего, будет ясной и теплой.\n'


      button_support1 = types.InlineKeyboardButton('🎁Поддержать проект (DonationAlerts)', url='https://www.donationalerts.com/r/pogodaradar')
      button_support2 = types.InlineKeyboardButton('💶Поддержать проект (CloudTips)', url='https://pay.cloudtips.ru/p/317d7868')
      button_support3 = types.InlineKeyboardButton('💳Поддержать проект (YooMoney)', url='https://yoomoney.ru/to/410018154591956')
      markup = types.InlineKeyboardMarkup().add(button_support1, button_support2, button_support3)
      markup = types.InlineKeyboardMarkup()
      markup.row(button_support1)
      markup.row(button_support2)
      markup.row(button_support3)

      bot.send_message(message.from_user.id, f'🏙️Погода в городе: {location}\n🗓️Время и дата: {local_time}\n\n🔄Данные обновлены: {update_current}\n\n{emoji} {condition}\n\n🌡️Температура: {temp_c}°C\n🤗По ощущениям: {feelslike_c}°C\n💨Скорость ветра: {wind_mps:.1f} м/с\n👉🏻Направление ветра: {wind_dir_text}\n💧Влажность: {humidity} %\n☁️Облачность: {clouds} %\n🕗Давление: {pressure} гПа\n🕶️Видимость: {vis_km} км\n\n😎UV индекс: {uv_index}\n\n🌅Восход солнца: {sunrise}\n🌇Закат солнца: {sunset}\n\nРекомендации по одежде: \n{clothing_recommendations}', reply_markup=markup)
  except KeyError:
      bot.send_message(message.from_user.id, 'Не удалось получить данные о погоде для данного города. Пожалуйста, попробуйте еще раз или укажите другой город.')

@bot.message_handler(commands=['help'])
def get_help(message):
  bot.send_message(message.from_user.id, 
    '(Техпомощь)\n'
    '1) ⚙️Команда /start - Начало работы с ботом\n'
    '2) 🚨Команда /help - Справка о работе с ботом\n'
    '3) 🛠️Команда /support - Связаться с техподдержкой бота\n\n'
    
    '(Погода)\n'
    '4) ✏️Команда /setcity - Изменить город\n'
    '5) ⛅Команда /nowweather - Текущая погода в городе\n'
    '6) 📆Команда /forecastweather - Прогноз погоды на 3 дня в городе\n'
    '7) ✈️Команда /weatherairports - Погода в аэропортах мира\n'
    '8) 🗺️Команда /radarmap - Радар осадков\n'
    '9) ⚠️Команда /alerts - Предупреждения о непогоде в городах по всему миру\n'
    '10) 🌫️Команда /aqi - Качество воздуха в городе\n'
    '11) ☔Команда /precipitationmap - Карта интенсивности осадков\n'
    '12) 🌡️Команда /anomaltempmap - Карта аномалии среднесуточной температуры за 5 суток\n'
    '13) 🌡️Команда /tempwatermap - Прогноз температуры воды в Черном море\n'
    '14) 📈Команда /verticaltemplayer - Вертикальное распределение температуры в нижнем 1-километровом слое\n'
    '15) 📊Команда /meteograms - Просмотр метеограмм по городам России и Беларуси\n'
    '16) 🌐Команда /weatherwebsites - Полезные сайты для просмотра информации о погоде\n'
    '17) 🔥Команда /firehazard_map - Карта пожароопаcности по РФ\n'
    '18) ❗Команда /extrainfo - Экстренная информация об ухудшении погодных условий\n'
    '19) 🚩Команда /stations - Информация о погоде с метеостанций РФ (бета-версия)\n'
    '20) 🌍Команда /get_meteoweb - Прогнозные карты погоды Meteoweb\n\n'
    
    '(Доп.настройки)\n'
    '21) 📢Команда /share - Поделиться ботом\n'
    '22) 🎁Команда /donate - Поддержать разработчика\n\n'

    '(Развлечения)\n'
    '23) 🎮Команда /guess_temp - Угадай загаданную температуру'
)
# echo-функция, которая показывает справку по работе с ботом

@bot.message_handler(commands=['share'])
def get_share(message):
  markup = types.InlineKeyboardMarkup()
  button_1 = (types.InlineKeyboardButton('Поделиться ботом', url = 'https://t.me/share/url?url=https://t.me/pogodaradar_bot'))
  markup.add(button_1)
  bot.send_message(message.from_user.id, text='<a href="https://t.me/share/url?url=https://t.me/pogodaradar_bot">PogodaRadar в Telegram</a>', parse_mode=ParseMode.HTML, reply_markup=markup)
  markup.add(button_1)

@bot.message_handler(commands=['donate'])
def get_donate(message):
  bot.send_message(
    message.from_user.id,
    (
        'Вы можете поддержать PogodaRadar по ссылкам:\n'
        '1) 🎁DonationAlerts: https://donationalerts.com/r/pogodaradar\n'
        '2) 💶CloudTips: https://pay.cloudtips.ru/p/317d7868\n'
        '3) 💳YooMoney: https://yoomoney.ru/to/410018154591956'
    ),
    disable_web_page_preview=True
)
# echo-функция, которая показывает ссылку на поддержку разработчика

@bot.message_handler(commands=['radarmap'])
def get_radar_map(message):
  url = 'https://meteoinfo.ru/hmc-output/rmap/phenomena.gif'
  response = requests.get(url)

  if response.status_code == 200:
   with open('phenomena.gif', 'wb') as f:
    f.write(response.content)

    with open('phenomena.gif', 'rb') as f:
        bot.send_animation(message.from_user.id, f)

    os.remove('phenomena.gif')
  else:
   bot.send_message(message.from_user.id, 'Не удалось загрузить изображение')
# echo-функция, которая показывает радар погоды

@bot.message_handler(commands=['precipitationmap'])
def get_precipitation_map(message):
  url = 'https://meteoinfo.ru/hmc-input/mapsynop/Precip.png'
  response = requests.get(url)

  if response.status_code == 200:
   with open('Precip.png', 'wb') as f:
    f.write(response.content)

    with open('Precip.png', 'rb') as f:
        bot.send_photo(message.from_user.id, f, caption='Карта осадков за прошедшие сутки')

    os.remove('Precip.png')
  else:
   bot.send_message(message.from_user.id, 'Не удалось загрузить изображение')
# echo-функция, которая показывает карту интенсивности осадков

@bot.message_handler(commands=['tempwatermap'])
def get_tempwater_map(message):
  url = "https://meteoinfo.ru/res/230/web/esimo/black/sst/black.png"
  response = requests.get(url)

  if response.status_code == 200:
   with open('black.png', 'wb') as f:
    f.write(response.content)

    with open('black.png', 'rb') as f:
        bot.send_animation(message.from_user.id, f)

    os.remove('black.png')
  else:
   bot.send_message(message.from_user.id, 'Не удалось загрузить изображение')
# echo-функция, которая показывает карты температура воздуха в черном море

@bot.message_handler(commands=['verticaltemplayer'])
def get_vertical_temp(message):
  url = "https://meteoinfo.ru/hmc-input/profiler/cao/image1.jpg"
  response = requests.get(url)

  if response.status_code == 200:
   with open('image1.png', 'wb') as f:
    f.write(response.content)

    with open('image1.png', 'rb') as f:
        bot.send_photo(message.from_user.id, f, "Измерения проведены с помощью оборудования компании НПО АТТЕХ. Координаты профилемера: ФГБУ Центральная аэрологическая обсерватория, Московская обл., г. Долгопрудный, ул. Первомайская, 3 (55°55´32´´N, 37°31´23´´E)")

    os.remove('image1.png')
  else:
   bot.send_message(message.from_user.id, 'Не удалось загрузить изображение')
# echo-функция, которая показывает карты температура воздуха в 1-км слое

@bot.message_handler(commands=['anomaltempmap'])
def get_anomal_temp_map(message):
  url = 'https://meteoinfo.ru/images/vasiliev/anom2_6/anom2_6.gif'
  response = requests.get(url)

  if response.status_code == 200:
      with open('anom2_6.gif', 'wb') as f:
          f.write(response.content)

      with open('anom2_6.gif', 'rb') as f:
          bot.send_photo(message.from_user.id, photo=f)

      os.remove('anom2_6.gif')
  else:
      bot.send_message(message.from_user.id, 'Не удалось загрузить изображение')
# echo-функция, которая показывает карту аномалии сред.суточной температуры

@bot.message_handler(commands=['nowweather'])

def convert_to_mps(kph):
  mps = kph * 1000 / 3600
  return mps

def get_wind_direction(deg):
  directions = {
      "N": "Северный",
      "NNE": "Северо-северо-восточный",
      "NE": "Северо-восточный",
      "ENE": "Восточно-северо-восточный",
      "E": "Восточный",
      "ESE": "Восточно-юго-восточный",
      "SE": "Юго-восточный",
      "SSE": "Юго-юго-восточный",
      "S": "Южный",
      "SSW": "Юго-юго-западный",
      "SW": "Юго-западный",
      "WSW": "Западно-юго-западный",
      "W": "Западный",
      "WNW": "Западно-северо-западный",
      "NW": "Северо-западный",
      "NNW": "Северо-северо-западный"
  }

  return directions.get(deg, 'Неизвестное направление')


def now_weather(message):
  # Загружаем город пользователя из CSV
  city = load_city(message.from_user.id)
  if city is None:
        bot.send_message(message.from_user.id, 'Город не установлен. Пожалуйста, сначала используйте команду /setcity, чтобы установить город.')
        return
    
  parameters = {'key': api_key, 'q': city, 'lang': 'ru'}
  r = requests.get(f'{weather_url}/current.json', params=parameters)

  data = r.json()

  astronomy_parameters = {'key': api_key, 'q': city, 'lang': 'ru'}
  astronomy_r = requests.get(f'{weather_url}/astronomy.json', params=astronomy_parameters)

  astronomy_data = astronomy_r.json()

  try:
    location = data['location']['name'] + ', ' + data['location']['country']
    local_time = datetime.strptime(data['location']['localtime'], '%Y-%m-%d %H:%M').strftime('%d %B %Y %H:%M')
    update_current = datetime.strptime(data['current']['last_updated'], '%Y-%m-%d %H:%M').strftime('%d %B %Y %H:%M')
    months = {
      'January': 'Января',
      'February': 'Февраля',
      'March': 'Марта',
      'April': 'Апреля',
      'May': 'Мая',
      'June': 'Июня',
      'July': 'Июля',
      'August': 'Августа',
      'September': 'Сентября',
      'October': 'Октября',
      'November': 'Ноября',
      'December': 'Декабря'
    }
    local_time = ' '.join([months.get(month, month) for month in local_time.split()])
    update_current = ' '.join([months.get(month, month) for month in update_current.split()])

    
    condition_code = str(data['current']['condition']['code'])
    condition = data['current']['condition']['text']
    temp_c = data['current']['temp_c']
    feelslike_c = data['current']['feelslike_c']
    wind = data['current']['wind_kph']
    wind_dir = data['current']['wind_dir']
    humidity = data['current']['humidity']
    clouds = data['current']['cloud']
    pressure = int(data['current']['pressure_mb'])
    uv_index = int(data['current']['uv'])
    vis_km = data['current']['vis_km']
    sunrise = astronomy_data['astronomy']['astro']['sunrise'].replace('AM', 'Утра')
    sunset = astronomy_data['astronomy']['astro']['sunset'].replace('PM', 'Вечера')
    weather_icons = {
        '1000': '☀️',  # Sunny / Clear
        '1003': '🌤️',  # Partly cloudy
        '1006': '☁️',  # Cloudy
        '1009': '☁️',  # Overcast
        '1030': '🌫️',  # Mist
        '1063': '🌦️',  # Patchy rain possible
        '1066': '❄️',  # Patchy snow possible
        '1069': '🌨️',  # Patchy sleet possible
        '1072': '☔',  # Patchy freezing drizzle possible
        '1087': '🌩️',  # Thundery outbreaks possible
        '1114': '❄️🌬️',  # Blowing snow
        '1117': '❄️🌬️',  # Blizzard
        '1135': '🌫️',  # Fog
        '1147': '🌫️🥶',  # Freezing fog
        '1150': '🌧️',  # Patchy light drizzle
        '1153': '🌧️',  # Light drizzle
        '1168': '🌧️',  # Freezing drizzle
        '1171': '🌧️',  # Heavy freezing drizzle
        '1180': '🌧️',  # Patchy light rain
        '1183': '🌧️',  # Light rain
        '1186': '🌧️',  # Moderate rain at times
        '1189': '🌧️',  # Moderate rain
        '1192': '🌧️',  # Heavy rain at times
        '1195': '🌧️',  # Heavy rain
        '1198': '🌧️❄️',  # Light freezing rain
        '1201': '🌧️❄️',  # Moderate or heavy freezing rain
        '1204': '🌨️',  # Light sleet
        '1207': '🌨️',  # Moderate or heavy sleet
        '1210': '❄️',  # Patchy light snow
        '1213': '❄️',  # Light snow
        '1216': '❄️',  # Patchy moderate snow
        '1219': '❄️',  # Moderate snow
        '1222': '❄️',  # Patchy heavy snow
        '1225': '❄️',  # Heavy snow
        '1237': '🌨️',  # Ice pellets
        '1240': '🌧️',  # Light rain shower
        '1243': '🌧️',  # Moderate or heavy rain shower
        '1246': '🌧️',  # Torrential rain shower
        '1249': '🌨️',  # Light sleet showers
        '1252': '🌨️',  # Moderate or heavy sleet showers
        '1255': '❄️',  # Light snow showers
        '1258': '❄️',  # Moderate or heavy snow showers
        '1261': '🌨️',  # Light showers of ice pellets
        '1264': '🌨️',  # Moderate or heavy showers of ice pellets
        '1273': '⛈️',  # Patchy light rain with thunder
        '1276': '⛈️',  # Moderate or heavy rain with thunder
        '1279': '⛈️❄️',  # Patchy light snow with thunder
        '1282': '⛈️❄️',  # Moderate or heavy snow with thunder
    }
    emoji = weather_icons.get(condition_code, '✖️')
    wind_mps = convert_to_mps(wind)
    wind_dir_text = get_wind_direction(wind_dir)

    clothing_recommendations = ''

    # Temperature-based recommendations
    if temp_c < -10:
          clothing_recommendations += '❄️ Сильный мороз: Наденьте термобелье, утепленные штаны, пуховик или шубу, шапку-ушанку, шарф, теплые перчатки и зимнюю обувь с мехом.\n'
    elif -10 <= temp_c < 0:
          clothing_recommendations += '❄️ Мороз: Наденьте теплое пальто или пуховик, шапку, шарф, перчатки и утепленную обувь.\n'
    elif 0 <= temp_c < 10:
          clothing_recommendations += '🧥 Прохладно: Наденьте теплую куртку, свитер, джинсы или утепленные брюки, легкую шапку или капюшон.\n'
    elif 10 <= temp_c < 15:
          clothing_recommendations += '🧥 Легкая прохлада: Наденьте ветровку, джинсовку или толстовку, брюки или джинсы.\n'
    elif 15 <= temp_c < 20:
          clothing_recommendations += '👕 Комфортно: Наденьте легкую куртку или кардиган, футболку или рубашку, джинсы или брюки.\n'
    elif 20 <= temp_c < 25:
          clothing_recommendations += '👕 Тепло: Наденьте футболку, шорты или легкие брюки, можно взять с собой легкую кофту на случай ветра.\n'
    else:
          clothing_recommendations += '🔥 Жарко: Наденьте легкую одежду из дышащих тканей, шорты, майку или сарафан. Не забудьте головной убор и солнцезащитные очки.\n'

      # Wind-based recommendations
    if wind >= 40:
        clothing_recommendations += '🌬️ Сильный ветер: Рекомендуем надеть ветровку, плотную куртку и плотные брюки.\n'
    elif wind >= 20:
        clothing_recommendations += '💨 Умеренный ветер: Наденьте легкую блузку, рубашку или футболку и брюки.\n'

      # Humidity-based recommendations
    if humidity >= 90:
          clothing_recommendations += '🌧️ Очень высокая влажность: Наденьте водонепроницаемую куртку, непромокаемые штаны и резиновые сапоги. Возьмите зонт.\n'
    elif humidity >= 80:
          clothing_recommendations += '🌧️ Высокая влажность: Наденьте водонепроницаемую куртку и непромокаемую обувь.\n'
    elif humidity >= 60:
          clothing_recommendations += '💦 Повышенная влажность: Наденьте дышащую одежду и обувь, которая не промокает.\n'

      # Pressure-based recommendations
    if pressure <= 970:
          clothing_recommendations += '🌪️ Очень низкое давление: Наденьте непромокаемую одежду, возьмите зонт и дополнительный слой одежды на случай резких изменений погоды.\n'
    elif pressure <= 990:
          clothing_recommendations += '🌫️ Низкое давление: Возьмите с собой легкую куртку или свитер, чтобы утеплиться в случае похолодания.\n'
    elif pressure >= 1030:
          clothing_recommendations += '☀️ Высокое давление: Наденьте легкую одежду, так как погода, скорее всего, будет ясной и теплой.\n'

    
    button_support1 = types.InlineKeyboardButton('🎁Поддержать проект (DonationAlerts)', url='https://www.donationalerts.com/r/pogodaradar')
    button_support2 = types.InlineKeyboardButton('💶Поддержать проект (CloudTips)', url='https://pay.cloudtips.ru/p/317d7868')
    button_support3 = types.InlineKeyboardButton('💳Поддержать проект (YooMoney)', url='https://yoomoney.ru/to/410018154591956')
    markup = types.InlineKeyboardMarkup().add(button_support1, button_support2, button_support3)
    markup = types.InlineKeyboardMarkup()
    markup.row(button_support1)
    markup.row(button_support2)
    markup.row(button_support3)

    bot.send_message(message.from_user.id, f'🏙️Погода в городе: {location}\n🗓️Время и дата: {local_time}\n\n🔄Данные обновлены: {update_current}\n\n{emoji} {condition}\n\n🌡️Температура: {temp_c}°C\n🤗По ощущениям: {feelslike_c}°C\n💨Скорость ветра: {wind_mps:.1f} м/с\n👉🏻Направление ветра: {wind_dir_text}\n💧Влажность: {humidity} %\n☁️Облачность: {clouds} %\n🕗Давление: {pressure} гПа\n🕶️Видимость: {vis_km} км\n\n😎UV индекс: {uv_index}\n\n🌅Восход солнца: {sunrise}\n🌇Закат солнца: {sunset}\n\nРекомендации по одежде: \n{clothing_recommendations}', reply_markup=markup)
  except KeyError:
    bot.send_message(message.from_user.id, 'Не удалось получить данные о погоде для данного города. Пожалуйста, попробуйте еще раз или укажите другой город.')
# echo-функция, которая выводит погоду в городе

@bot.message_handler(commands=['forecastweather'])
def forecast_weather(message):
  # Загружаем город пользователя из CSV
  city = load_city(message.from_user.id)
  if city is None:
        bot.send_message(message.from_user.id, 'Город не установлен. Пожалуйста, сначала используйте команду /setcity, чтобы установить город.')
        return
    
  parameters = {'key': api_key, 'q': city, 'days': 3, 'lang': 'ru'}
  r = requests.get(f'{weather_url}/forecast.json', params=parameters)

  data = r.json()

  try:
      location = data['location']['name'] + ', ' + data['location']['country']
      forecast_message = f'🏙️Прогноз погоды в городе: {location}\n\n'

      for day in data['forecast']['forecastday']:
          months = {
            'January': 'Января',
            'February': 'Февраля',
            'March': 'Марта',
            'April': 'Апреля',
            'May': 'Мая',
            'June': 'Июня',
            'July': 'Июля',
            'August': 'Августа',
            'September': 'Сентября',
            'October': 'Октября',
            'November': 'Ноября',
            'December': 'Декабря'
          }
          date = day['date']
          date = datetime.strptime(day['date'], '%Y-%m-%d').strftime('%d %B %Y')
          date = ' '.join([months.get(month, month) for month in date.split()])
          condition_code = str(day['day']['condition']['code'])
          conditions = str(day['day']['condition']['text'])
          max_temp = str(day['day']['maxtemp_c'])
          min_temp = str(day['day']['mintemp_c'])
          wind = day['day']['maxwind_kph']
          totalprecip_mm = str(day['day']['totalprecip_mm'])
          weather_icons = {
            '1000': '☀️',  # Солнечно
            '1003': '🌤️',  # Переменная облачность
            '1006': '☁️',  # Облачно
            '1009': '☁️',  # Пасмурно
            '1030': '🌫️',  # Туман
            '1063': '🌦️',  # Возможен кратковременный дождь
            '1066': '❄️',  # Возможен небольшой снег
            '1069': '🌨️',  # Возможен мокрый снег
            '1072': '☔',  # Возможен моросящий дождь
            '1087': '🌩️',  # Возможны грозы
            '1114': '❄️',  # Снег
            '1117': '❄️🌬️', # Метель
            '1135': '🌫️', # Туман
            '1147': '🌫️🥶', # Ледяной туман
            '1150': '🌧️',  # Периодические прояснения с дождем
            '1153': '🌦️',  # Кратковременный дождь
            '1168': '🌦️',  # Местами кратковременный дождь
            '1171': '🌧️',  # Пройдет дождь
            '1180': '🌧️',  # Кратковременные осадки
            '1183': '🌧️',  # Местами кратковременные осадки
            '1186': '🌧️',  # Дождь
            '1189': '🌧️',  # Местами дождь
            '1192': '🌧️',  # Проливные дожди
            '1195': '🌧️',  # Проливной дождь
            '1198': '⛈️',  # Дождь с грозой
            '1201': '⛈️',  # Кратковременный ливень
            '1204': '⛈️',  # Местами кратковременный ливень
            '1207': '⛈️',  # Ливень
            '1210': '⛈️',  # Местами ливень
            '1213': '⛈️',  # Красивая гроза
            '1216': '⛈️',  # Гроза
            '1219': '⛈️',  # Местами гроза
            '1222': '🌧️',  # Прохладные дожди
            '1225': '🌧️',  # Прохладно с дождем
            '1237': '🌨️',  # Гроза с мокрым снегом
            '1240': '🌨️',  # Кратковременный снег
            '1243': '🌨️',  # Местами кратковременный снег
            '1246': '🌨️',  # Снег
            '1249': '🌨️',  # Местами снег
            '1252': '🌨️',  # Эпизодический кратковременный снег
            '1255': '🌨️',  # Эпизодический снег
            '1258': '🌨️',  # Снегопад
            '1261': '🌨️',  # Местами снегопад
            '1264': '🌨️',  # Значительный снегопад
            '1273': '🌧️',  # Дождь с мокрым снегом
            '1276': '❄️',  # Кратковременные осадки / мокрый снег
            '1279': '❄️',  # Отдельные кратковременные осадки
            '1282': '❄️',  # Сыро
          }
          emoji = weather_icons.get(condition_code, '✖️')

          wind_mps_forecast = convert_to_mps(wind)

          forecast_message += f'🗓️Дата: {date}\n\n☔Погодные условия: {emoji}{conditions}\n🌡️Температура: Днем {max_temp}°C Ночью {min_temp}°C\n💨Ветер: {wind_mps_forecast:.1f} м/с\n💦Общая сумма осадков за день: {totalprecip_mm} мм\n\n'

        
      bot.send_message(message.from_user.id, forecast_message)
  except KeyError:
      bot.send_message(message.from_user.id, 'Не удалось получить данные о погоде для данного города. Пожалуйста, попробуйте еще раз или укажите другой город.')
# echo-функция, которая выводит прогноз погоды в городе

# Команда /aqi для получения данных о качестве воздуха
@bot.message_handler(commands=['aqi'])
def get_city_aqi(message):
    # Загружаем город пользователя из CSV
    city = load_city(message.from_user.id)
    if city is None:
        bot.send_message(message.from_user.id, 'Город не установлен. Пожалуйста, сначала используйте команду /setcity, чтобы установить город.')
        return

    # Запрашиваем данные о качестве воздуха
    parameters = {'key': api_key, 'q': city, 'aqi': 'yes', 'lang': 'ru'}
    r = requests.get(f'{weather_url}/current.json', params=parameters)

    try:
        data = r.json()
        location = data['location']['name'] + ', ' + data['location']['country']
        us_epa_index = str(data['current']['air_quality']['us-epa-index'])
        co = str(data['current']['air_quality']['co'])
        no2 = str(data['current']['air_quality']['no2'])
        o3 = str(data['current']['air_quality']['o3'])
        so2 = str(data['current']['air_quality']['so2'])
        pm2_5 = str(data['current']['air_quality']['pm2_5'])
        pm10 = str(data['current']['air_quality']['pm10'])

        bot.send_message(
            message.from_user.id,
            f'🏙️Качество воздуха в городе: {location}\n\n'
            f'🌿Уровень индекса: ( {us_epa_index} )\n\n'
            f'🏭🔥Среднее значение CO: {co}\n'
            f'🚗🚢Среднее значение NO2: {no2}\n'
            f'🌇Среднее значение O3: {o3}\n'
            f'🏭🌋Среднее значение SO2: {so2}\n'
            f'🏭🚜Среднее значение PM2.5: {pm2_5}\n'
            f'🏭🚜Среднее значение PM10: {pm10}'
        )
    except KeyError:
        bot.send_message(message.from_user.id, 'Ошибка получения данных о качестве воздуха. Пожалуйста, попробуйте еще раз или укажите другой город.')
# echo-функция, которая выводит качество воздуха в городе

@bot.message_handler(commands=['alerts'])
def alerts_weather(message):
    # Загружаем город пользователя из CSV
    city = load_city(message.from_user.id)
    if city is None:
        bot.send_message(message.from_user.id, 'Город не установлен. Пожалуйста, сначала используйте команду /setcity, чтобы установить город.')
        return

    parameters = {'key': api_key, 'q': city, 'days': 1, 'alerts': 'yes', 'lang': 'ru'}
    r = requests.get(f'{weather_url}/forecast.json', params=parameters)
    data = r.json()

    try:
        location = data['location']['name'] + ', ' + data['location']['country']
        months = {
          'January': 'Января',
          'February': 'Февраля',
          'March': 'Марта',
          'April': 'Апреля',
          'May': 'Мая',
          'June': 'Июня',
          'July': 'Июля',
          'August': 'Августа',
          'September': 'Сентября',
          'October': 'Октября',
          'November': 'Ноября',
          'December': 'Декабря'
        }
        local_time = datetime.strptime(data['location']['localtime'], '%Y-%m-%d %H:%M').strftime('%d %B %Y %H:%M')
        local_time = ' '.join([months.get(month, month) for month in local_time.split()])

        alerts_message = f'🏙️Предупреждения в городе: {location}\n🗓️Время и дата: {local_time}\n\n'

      
        for i in range(len(data['alerts']['alert'])):  # Display only alerts 0 and 1
                alert = data['alerts']['alert'][i]
                event = alert.get('event', 'Unknown Event')
                if not re.search(r'[а-яА-Я]', event):  
                    continue
                desc = alert.get('desc', 'No Description')
                effective = datetime.strptime(alert.get('effective', 'Unknown Effective Time'), '%Y-%m-%dT%H:%M:%S%z').strftime('%d %B %Y %H:%M (МСК)')
                expires = datetime.strptime(alert.get('expires', 'Unknown Expiry Time'), '%Y-%m-%dT%H:%M:%S%z').strftime('%d %B %Y %H:%M (МСК)')
                effective = ' '.join([months.get(month, month) for month in effective.split()])
                expires = ' '.join([months.get(month, month) for month in expires.split()])


                alerts_message += f'⚠️Предупреждение: {event}\n📝Описание: {desc}\n🕙Начальное время: {effective}\n🕓Конечное время: {expires}\n\n'
              
        bot.send_message(message.from_user.id, alerts_message)
    except KeyError:
        bot.send_message(message.from_user.id, f'Ошибка данных. Попробуйте другой город!')
# echo-функция, которая выводит предупреждения о непогоде

@bot.message_handler(commands=['weatherwebsites'])
def websites_weather(message):
  bot.send_message(message.from_user.id, 'Полезные сайты для просмотра погоды:\n\n1) ⚡Система грозопеленгации для отслеживания молний по всему миру: https://map.blitzortung.org/#5.13/56.37/40.11\n\n2) 🛰️Просмотр архивных спутниковых снимков по Европе и России: https://zelmeteo.ru\n\n3) 📊Сайт для просмотра прогноза погоды прогностических моделей по всему миру: https://meteologix.com')
#echo-функция, которая выводит ссылки на сайты погоды

def get_icao_code_by_name(airport_name):
  # Пример: простое сопоставление названия и ICAO-кода
  airports = {
      # Россия
      "шереметьево": "UUEE",
      "домодедово": "UUDD",
      "внуково": "UUWW",
      "жуковский": "UUBW",
      "абакан": "UNAA",
      "анадырь": "UHMA",
      "анапа": "URKA",
      "апатиты": "ULMK",
      "архангельск": "ULAA",
      "астрахань": "URWA",
      "барнаул": "UNBB",
      "белгород": "UUOB",
      "березово": "USHB",
      "благовещенск": "UNEE",
      "брянск": "UUBP",
      "бугульма": "UWKB",
      "великий устюг": "ULWU",
      "великий новгород": "ULNN",
      "владикавказ": "URMO",
      "владивосток": "UHWW",
      "волгоград": "URWW",
      "вологда": "ULWW",
      "воронеж": "UUOO",
      "воркута": "UUYW",
      "геленджик": "URKG",
      "горно-алтайск": "UNBG",
      "грозный": "URMG",
      "екатеринбург": "USSS",
      "игарка": "UOII",
      "ижевск": "USHH",
      "иркутск": "UIII",
      "йошкар-ола": "UWKJ",
      "казань": "UWKD",
      "калининград": "UMKK",
      "калуга": "UUBC",
      "кемерово": "UNEE",
      "киров": "USKK",
      "кострома": "UUBA",
      "краснодар": "URKK",
      "красноярск": "UNKL",
      "курган": "USUU",
      "курск": "UUOK",
      "кызыл": "UNKY",
      "липецк": "UUOL",
      "магнитогорск": "USCM",
      "махачкала": "URML",
      "минеральные воды": "URMM",
      "мурманск": "ULMM",
      "надым": "USMN",
      "нальчик": "URMN",
      "нижневартовск": "USNN",
      "нижнекамск": "UWKN",
      "нижний новгород": "UWGG",
      "новокузнецк": "UNWW",
      "новосибирск": "UNCC",
      "новый уренгой": "USMU",
      "омск": "UNOO",
      "оренбург": "UWOO",
      "орск": "UWOR",
      "пенза": "UWPP",
      "пермь": "USPP",
      "петрозаводск": "ULPB",
      "петропавловск-камчатский": "UHPP",
      "псков": "ULOO",
      "ростов-на-дону": "URRR",
      "рязань": "UWDR",
      "самара": "UWWW",
      "пулково": "ULLI",
      "саранск": "UWPS",
      "саратов": "UWSS",
      "сочи": "URSS",
      "ставрополь": "URMT",
      "сургут": "USRR",
      "сыктывкар": "UUYY",
      "тамбов": "UUOT",
      "томск": "UNTT",
      "тюмень": "USTR",
      "ульяновск": "UWLL",
      "уфа": "UWUU",
      "хабаровск": "UHHH",
      "ханты-мансийск": "USHN",
      "чебоксары": "UWKS",
      "челябинск": "USCC",
      "череповец": "ULWC",
      "чита": "UITA",
      "южно-сахалинск": "UHSS",
      "якутск": "UEEE",
      "ярославль": "UUDL",

      # Беларусь
      "минск": "UMMS",
      "минск-1": "UMMM",
      "брест": "UMBB",
      "витебск": "UMII",
      "гомель": "UMGG",
      "гродно": "UMMG",
      "могилев": "UMOO",
  }
  return airports.get(airport_name.lower())

@bot.message_handler(commands=['weatherairports'])
def get_airport_weather(message):
    msg5 = bot.send_message(message.from_user.id, 'Введите код или название аэропорта (например, UUEE или Шереметьево)')
    bot.register_next_step_handler(msg5, display_airport_weather)

def display_airport_weather(message, bot=bot):
    user_input = message.text.strip().upper()

    if len(user_input) == 4 and user_input.isalpha():
        airport_code = user_input
    else:
        airport_code = get_icao_code_by_name(user_input)

    if not airport_code:
        bot.send_message(message.from_user.id, "Не удалось найти аэропорт по этому названию. Попробуйте еще раз.")
        return

    api_airport_url = f'https://metartaf.ru/{airport_code}.json'
    response = requests.get(api_airport_url)

    if response.status_code == 200:
        data = response.json()
        weather_info = f"🌐 Кодировка аэропорта: {data['icao']}\n\n"
        weather_info += f"✈️ Погодные условия в аэропорту: {data['name']}\n\n"
        weather_info += f"📍 METAR-сводка по аэропорту: `{data['metar']}`\n"
        weather_info += f"🌀 TAF-прогноз по аэропорту: `{data['taf']}`\n"

        # Создаем клавиатуру
        inline_keyboard = types.InlineKeyboardMarkup()

        decode_can = types.InlineKeyboardButton("Как расшифровать данные?", callback_data='how_to_decode')

        inline_keyboard.add(decode_can)

        bot.send_message(
            message.chat.id,
            weather_info,
            reply_markup=inline_keyboard,
            parse_mode="MARKDOWN"
        )

        # Обработчик кнопки "Как расшифровать данные?"
        @bot.callback_query_handler(func=lambda call: call.data == 'how_to_decode')
        def handle_how_to_decode(callback):
            how_to_message = (
                "🛠 Как расшифровать METAR и TAF самостоятельно:\n\n"
                "📄 **METAR** — это закодированное сообщение о текущей погоде на аэродроме. "
                "Основные элементы METAR:\n"
                "- ICAO-код аэропорта (например, UUEE — Шереметьево).\n"
                "- Время составления прогноза (например, 121200Z — 12-е число, 12:00 UTC).\n"
                "- Погодные условия: облачность, видимость, осадки (например, SCT030 — разбросанные облака на высоте 3000 футов).\n"
                "- Ветер: направление и скорость (например, 18010KT — ветер с юга, 10 узлов).\n\n"
                "📄 **TAF** — это прогноз погоды для аэродрома на определенный период. "
                "Он содержит информацию о ветре, видимости, облаках и других условиях. "
                "Ключевые элементы TAF:\n"
                "- Время действия прогноза (например, 1212/1312 — с 12:00 12-го числа до 12:00 13-го числа).\n"
                "- Изменения погоды: TEMPO, BECMG, PROB (например, TEMPO 1418 — временные изменения с 14:00 до 18:00).\n\n"
                "📌 Для детального разбора каждого элемента вы можете воспользоваться ссылкой:\n"
                "- [Ссылка для расшифровки METAR и TAF](https://www.iflightplanner.com/resources/metartaftranslator.aspx)\n"
            )
            bot.send_message(
                callback.message.chat.id,
                how_to_message,
                parse_mode="MARKDOWN",
                disable_web_page_preview=True
            )
    else:
        bot.send_message(
            message.chat.id,
            "Не удалось получить информацию о погоде для данного аэропорта. "
            "Пожалуйста, попробуйте еще раз или укажите другой код аэропорта."
        )
# echo-функция, которая выводит погодные условия для аэропортов

@bot.message_handler(commands=['meteograms'])
def start_meteogram_request(message):
    # Создаем инлайн-клавиатуру с двумя кнопками: "Один город" и "Несколько городов"
    keyboard = types.InlineKeyboardMarkup()
    one_city_btn = types.InlineKeyboardButton(text="Один город", callback_data="one_city")
    several_cities_btn = types.InlineKeyboardButton(text="Несколько городов", callback_data="several_cities")
    keyboard.add(one_city_btn, several_cities_btn)

    bot.send_message(message.chat.id, "Выберите режим:", reply_markup=keyboard)

# Обрабатываем нажатие кнопок
@bot.callback_query_handler(func=lambda call: call.data in ["one_city", "several_cities"])
def choose_city_mode(call):
    if call.data == "one_city":
        bot.send_message(call.message.chat.id, "Введите название города")
        bot.register_next_step_handler(call.message, send_meteogram)  # Переход к запросу одного города
    elif call.data == "several_cities":
        bot.send_message(call.message.chat.id, "Введите названия городов через запятую (⚠️Максимум 10 городов)")
        bot.register_next_step_handler(call.message, send_several_meteograms)  # Переход к запросу нескольких городов

def send_meteogram(message):
    start_time = time.time()
    city_name = message.text.strip().upper()

    city_info = next((city for city in city_data if city['eng_name'] == city_name), None)

    if city_info:
        city_url = city_info['url']
        response = requests.get(city_url)

        if response.status_code == 200:
            end_time = time.time()
            elapsed_time = end_time - start_time
            bot.send_photo(message.chat.id, response.content, caption=f'Прогноз на 5 дней для города: {city_name.capitalize()}\nВремя затраченное на отправку: {elapsed_time:.2f} секунд')
        else:
            bot.reply_to(message, "Ошибка загрузки данных!")
    else:
        bot.reply_to(message, "Город не найден")

    # После отправки метеограммы предлагаем снова выбрать режим
    start_meteogram_request(message)

def send_several_meteograms(message):
    start_time = time.time()
    cities = [city.strip().upper() for city in message.text.split(',') if city.strip()]  # Разбиваем строку на список городов
    cities = cities[:10]  # Ограничиваем список до 10 городов

    if not cities:
        bot.reply_to(message, "Не указано ни одного города. Попробуйте снова.")
        start_meteogram_request(message)
        return

    for city_name in cities:
        city_info = next((city for city in city_data if city['eng_name'] == city_name), None)

        if city_info:
            city_url = city_info['url']
            response = requests.get(city_url)

            if response.status_code == 200:
                end_time = time.time()
                elapsed_time = end_time - start_time
                bot.send_photo(message.chat.id, response.content, caption=f'Прогноз на 5 дней для города: {city_name.capitalize()}\nВремя затраченное на отправку: {elapsed_time:.2f} секунд')
            else:
                bot.reply_to(message, f"Ошибка загрузки данных для города {city_name}.")
        else:
            bot.reply_to(message, f"Город {city_name} не найден.")

    # После отправки всех метеограмм предлагаем снова выбрать режим
    start_meteogram_request(message)

# echo-функция, которая отправляет метеограммы с сайта meteorf

def get_fmeteo_image_and_info(run_time, forecast_hour, map_type="prec"):
    """
    Получает изображение и информацию о дате и типе прогноза с fmeteo.ru.

    Args:
        run_time (str): Время прогона (00, 06, 12, 18).
        forecast_hour (str): Время карты по часам (003, 006, ..., 384).
        map_type (str): Тип карты (prec, temp, temp8, 850hpa, cloudst, cloudsh, wind, licape, snd, tef).

    Returns:
        tuple: (URL изображения, информация о прогнозе) или (сообщение об ошибке, None).
    """

    # Определение кода и названия типа карты
    type_mapping = {
        "prec": ("prec", "🌧️ Осадки"),
        "temp": ("temp", "🌡️ Температура у поверхности 2м"),
        "temp8": ("temp8", "🌡️ Температура на уровне 850 гПа"),
        "cloudst": ("cloudst", "☁️ Низкая-средняя облачность"),
        "cloudsh": ("cloudsh", "☁️ Верхняя облачность"),
        "wind": ("wind", "💨 Ветер"),
        "licape": ("licape", "⚡ Параметры неустойчивости"),
        "snd": ("snd", "❄️ Высота снежного покрова"),
        "tef": ("tef", "🌡️ Эффективная температура")
    }

    if map_type not in type_mapping:
        return f"Ошибка: неверный тип карты для fmeteo. Поддерживаются: {', '.join(type_mapping.keys())}", None

    type_code, map_type_text = type_mapping[map_type]
    url = f"http://fmeteo.ru/gfs/{run_time}/{type_code}_{forecast_hour}.png"
    headers = {"Cache-Control": "no-cache"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # Расчет даты и времени прогноза
        run_time_hour = int(run_time)
        forecast_hour_int = int(forecast_hour)
        current_date = datetime.utcnow()

        forecast_date = current_date.replace(hour=run_time_hour, minute=0, second=0, microsecond=0)

        # Корректировка даты, если текущее время уже прошло время прогона
        if current_date.hour >= run_time_hour:
            forecast_date = forecast_date
        else:
            forecast_date -= timedelta(days=1)

        forecast_date += timedelta(hours=forecast_hour_int)
        forecast_date_str = forecast_date.strftime("%Y-%m-%d %H:%M") + " UTC"

        info = f"📅 Прогноз погоды на {forecast_date_str}"
        return url, info, map_type_text
    else:
        return f"Ошибка: невозможно получить данные для карты {map_type} за {forecast_hour} часов.", None, None

# Обновление обработки команды /get_meteoweb для учета новых типов карт и многопоточности
@bot.message_handler(commands=['get_meteoweb'])
def get_map_command(message):
    """
    Обработчик команды /get_meteoweb. Запрашивает у пользователя параметры прогноза
    и выводит прогнозные карты в соответствии с запросом.
    """
    instruction = (
    "🌍 *Команда /get_meteoweb* — ваш помощник для получения прогнозных карт погоды от Meteoweb!\n\n"
    "📝 *Как использовать:*\n"
    "Введите параметры карты в формате:\n"
    "`время_прогона начальный_час конечный_час тип_карты`\n\n"
    "🔍 *Примеры запросов:*\n"
    "• `00 003 027 prec` — карта осадков с 3 по 27 час прогноза.\n"
    "• `12 006 036 temp` — карта температуры у поверхности с 6 по 36 час.\n"
    "• `00 003 024 temp8` — карта температуры на уровне 850 гПа с 3 по 24 час.\n\n"
    "📊 *Доступные типы карт:*\n"
    "• `prec` — осадки 🌧️\n"
    "• `temp` — температура у поверхности 🌡️\n"
    "• `temp8` — температура на уровне 850 гПа 🗻\n"
    "• `cloudst` — общая облачность ☁️\n"
    "• `cloudsh` — высокая облачность 🌫️\n"
    "• `wind` — ветер 🌬️\n"
    "• `licape` — индекс неустойчивости (LICAPE) ⚡\n"
    "• `snd` — снежный покров ❄️\n"
    "• `tef` — температура эффективная 🌡️\n\n"
    "⚠️ *Важные ограничения:*\n"
    "• За один запрос можно получить не более 10 карт.\n"
    "• Если нужно больше карт, повторите команду.\n\n"
    )
    msg = bot.send_message(message.chat.id, instruction, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_map_request)

def calculate_forecast_time(run_time, forecast_hour):
  """
  Рассчитывает время прогноза на основе времени прогона и прогнозного часа.
  """
  # Преобразуем строковое время прогона в целое число (00, 06, 12, 18)
  run_time_hour = int(run_time)
  # Преобразуем строковое время прогноза в целое число
  forecast_hour = int(forecast_hour)
  # Получаем текущее время UTC
  current_date = datetime.utcnow()

  # Устанавливаем время прогона на базе текущей даты и времени
  forecast_date = current_date.replace(hour=run_time_hour, minute=0, second=0, microsecond=0)

  # Если текущее время меньше времени прогона, корректируем на предыдущий день
  if current_date.hour < run_time_hour:
      forecast_date -= timedelta(days=1)
  # Добавляем прогнозные часы к дате прогона
  forecast_date += timedelta(hours=forecast_hour)

  # Возвращаем строку с датой и временем прогноза в формате UTC
  return forecast_date.strftime("%Y-%m-%d %H:%M") + " UTC"

def process_map_request(message):
  try:
      # Разделение введенных пользователем параметров
      parts = message.text.split()
      if len(parts) != 4:
          raise ValueError("Неверное количество параметров. Ожидается: время прогона, начальный час, конечный час, тип карты.")

      # Получение параметров
      run_time = parts[0]
      start_hour = int(parts[1])
      end_hour = int(parts[2])
      map_type = parts[3].lower()

      # Проверка допустимости времени прогона
      if run_time not in ["00", "06", "12", "18"]:
          raise ValueError("Неверное время прогона. Допустимые значения: 00, 06, 12, 18.")

      # Проверка допустимости начального и конечного времени
      if not (3 <= start_hour <= 384 and start_hour % 3 == 0):
          raise ValueError("Некорректное начальное время прогноза. Время должно быть от 003 до 384 с шагом в 3 часа.")

      if not (3 <= end_hour <= 384 and end_hour % 3 == 0):
          raise ValueError("Некорректное конечное время прогноза. Время должно быть от 003 до 384 с шагом в 3 часа.")

      if start_hour > end_hour:
          raise ValueError("Начальное время не может быть больше конечного.")

      # Проверка допустимости типа карты
      if map_type not in ["prec", "temp", "temp8", "cloudst", "cloudsh", "wind", "licape", "snd", "tef"]:
          raise ValueError(f"Неверный тип карты. Допустимые значения: prec, temp, temp8, cloudst, cloudsh, wind, licape, snd, tef.")

      # Список часов для прогноза с шагом 3
      forecast_hours = list(range(start_hour, end_hour + 1, 3))

      # Ограничение на количество карт за один запрос
      max_images_per_request = 10
      if len(forecast_hours) > max_images_per_request:
          bot.send_message(
              message.chat.id,
              f"⚠️ Запрос превышает лимит: можно получить только {max_images_per_request} карт за один запрос. "
              f"Попробуйте уменьшить диапазон времени."
          )
          return

      # Многопоточное получение карт
      with concurrent.futures.ThreadPoolExecutor() as executor:
          futures = [
              executor.submit(get_fmeteo_image_and_info, run_time, f"{hour:03}", map_type)
              for hour in forecast_hours
          ]
          results = [future.result() for future in futures]

      # Разделение на группы по 10 карт и отправка
      for i in range(0, len(results), max_images_per_request):
          chunk = results[i:i + max_images_per_request]
          media_group = []

          # Формируем общую подпись для всех карт
          map_type_text = None

          for result in chunk:
            # Убедимся, что структура кортежа корректна
            if len(result) == 3:
                url, info, current_map_type_text = result
            else:
                # Если структура неожиданная, пропускаем элемент
                bot.send_message(message.chat.id, "Ошибка: некорректный формат данных.")
                continue

            # Проверяем, что URL корректен
            if url.startswith("http"):
                # Устанавливаем тип карты (map_type_text) только один раз
                if map_type_text is None:
                    map_type_text = current_map_type_text
                # Добавляем изображение в группу медиа
                media_group.append(InputMediaPhoto(url, caption=info))
            else:
                # Если произошла ошибка, отправляем сообщение о ней
                bot.send_message(message.chat.id, url)

          months = {
            'January': 'Января',
            'February': 'Февраля',
            'March': 'Марта',
            'April': 'Апреля',
            'May': 'Мая',
            'June': 'Июня',
            'July': 'Июля',
            'August': 'Августа',
            'September': 'Сентября',
            'October': 'Октября',
            'November': 'Ноября',
            'December': 'Декабря'
          }

          # Формируем начальную и конечную даты прогноза
          start_forecast_time = calculate_forecast_time(run_time, start_hour).replace(" UTC", "")
          end_forecast_time = calculate_forecast_time(run_time, end_hour).replace(" UTC", "")

          start_forecast_date = datetime.strptime(start_forecast_time, "%Y-%m-%d %H:%M")
          end_forecast_date = datetime.strptime(end_forecast_time, "%Y-%m-%d %H:%M")

          # Формируем строки с датой и временем прогноза в формате с английскими месяцами
          start_forecast_date_str = start_forecast_date.strftime("%d %B %Y %H:%M") + " UTC"
          end_forecast_date_str = end_forecast_date.strftime("%d %B %Y %H:%M") + " UTC"

          # Заменяем английские месяцы на русские
          for eng_month, rus_month in months.items():
              start_forecast_date_str = start_forecast_date_str.replace(eng_month, rus_month)
              end_forecast_date_str = end_forecast_date_str.replace(eng_month, rus_month)

          # Формируем общую подпись для всех карт
          caption = f"📅 Прогноз погоды с {start_forecast_date_str} по {end_forecast_date_str}\n"
          if map_type in ["prec", "temp", "temp8", "cloudst", "cloudsh", "wind", "licape", "snd", "tef"]:
              caption += f"Тип карты: {map_type_text}\n"
          else:
              caption += "Тип карты: неизвестен\n"

          if media_group:
              try:
                  # Отправляем группу изображений
                  bot.send_media_group(message.chat.id, media_group)
                  # Отправляем общую подпись после отправки группы
                  bot.send_message(message.chat.id, caption)
              except Exception as e:
                  # Логируем и отправляем сообщение об ошибке
                  bot.send_message(message.chat.id, f"Ошибка при отправке изображений: {e}")

  except ValueError as e:
          # Обработка ошибок валидации пользовательских данных
          bot.send_message(
              message.chat.id,
              f"Ошибка: {e}.\n\n"
              "Пожалуйста, следуйте формату: `время_прогона начальный_час конечный_час тип_карты`\n"
              "Примеры:\n"
              "`00 003 027 prec`\n"
              "`12 006 036 temp`\n"
              "`00 003 024 temp8`",
              parse_mode="Markdown",
          )

  except Exception as e:
          # Обработка других исключений
          bot.send_message(message.chat.id, f"Произошла ошибка: {e}")
# echo-функция отправки карт метеовеб

@bot.message_handler(commands=['firehazard_map'])
def get_firehazard_map(message):
  url = "https://meteoinfo.ru/images/vasiliev/plazma_ppo3.gif"
  response = requests.get(url)

  if response.status_code == 200:
   with open('plazma_ppo3.gif', 'wb') as f:
    f.write(response.content)

    with open('plazma_ppo3.gif', 'rb') as f:
        bot.send_animation(message.from_user.id, f, caption='Карта пожароопасности по РФ')

    os.remove('plazma_ppo3.gif')
  else:
   bot.send_message(message.from_user.id, 'Не удалось загрузить изображение')
# echo-функция, которая показывает карту пожароопасности по РФ

def get_extrainfo():
    url = 'https://meteoinfo.ru/extrainfopage'

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return "Ошибка при запросе данных.", ["Не удалось получить экстренную информацию."], "Нет дополнительной информации."

    soup = BeautifulSoup(response.text, 'html.parser')

    # Извлекаем заголовок страницы
    page_header = soup.find('div', class_='page-header')
    headline = page_header.find('h1').text.strip() if page_header and page_header.find('h1') else "Экстренная информация"

    # Ищем таблицу с экстренной информацией в блоке 'div_1'
    extrainfo = []
    info_blocks = soup.find_all('div', id='div_1')

    for block in info_blocks:
        rows = block.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            if cell_texts:
                extrainfo.append(" | ".join(cell_texts))

    # Ограничиваем количество сообщений до 5
    extrainfo = extrainfo[:7] if extrainfo else ["Нет экстренной информации."]

    # Ищем блок с дополнительной информацией в 'div_2'
    additional_info = []
    div_2 = soup.find('div', id='div_2')
    if div_2:
        rows = div_2.find_all('tr')
        for row in rows:
            cell = row.find('td')
            if cell and cell.text.strip():
                additional_info.append(cell.text.strip())

    additional_info_text = "\n".join(additional_info) if additional_info else "Нет дополнительной информации."

    return headline, extrainfo, additional_info_text


# Обработчик команды /extrainfo
@bot.message_handler(commands=['extrainfo'])
def send_extrainfo(message):
    try:
        # Получаем данные
        headline, extrainfo, additional_info = get_extrainfo()

        # Формируем сообщение
        combined_message = f"⚠️ <b>{headline}</b> ⚠️\n\n" + "\n\n".join(extrainfo)
        combined_message += "\n\n— — —\n\n" + additional_info

        # Отправляем сообщение
        bot.send_message(message.chat.id, combined_message, parse_mode='HTML')
    except Exception as e:
        # Обработчик ошибок
        bot.send_message(message.chat.id, f"Произошла ошибка: {str(e)}", parse_mode='HTML')
# echo-функция, которая отвечает за экстренную информацию гидрометцентра

# Функция для получения данных о погоде с сайта
regions_dict = {
    "адыгея республика": "republic-adygea",
    "алтай республика": "republic-altai",
    "алтайский край": "territory-altai",
    "амурская область": "amur-area",
    "архангельская область": "arkhangelsk-area",
    "астраханская область": "astrakhan-area",
    "башкортостан республика": "republic-bashkortostan",
    "белгородская область": "belgorod-area",
    "брянская область": "bryansk-area",
    "бурятия республика": "republic-buryatia",
    "владимирская область": "vladimir-area",
    "волгоградская область": "volgograd-area",
    "вологодская область": "vologda-area",
    "воронежская область": "voronezh-area",
    "дагестан республика": "republic-dagestan",
    "донецкая народная республика": "republic-donetsk",
    "еврейская автономная область": "evr-avt-obl",
    "забайкальский край": "territory-zabaykalsky",
    "запорожская область": "zaporizhzhia-area",
    "ивановская область": "ivanovo-area",
    "ингушетия республика": "republic-ingushetia",
    "иркутская область": "irkutsk-area",
    "кабардино-балкария республика": "republic-kabardino-balkaria",
    "калининградская область": "kaliningrad-area",
    "калмыкия республика": "republic-kalmykia",
    "калужская область": "kaluga-area",
    "камчатский край": "territory-kamchatka",
    "карачаево-черкесия": "republic-karachay-cherkessia",
    "карелия республика": "republic-karelia",
    "кемеровская область": "kemerovo-area",
    "кировская область": "kirov-area",
    "коми республика": "republic-komi",
    "костромская область": "kostroma-area",
    "краснодарский край": "krasnodar-territory",
    "красноярский край": "territory-krasnoyarsk",
    "крым республика": "republic-crimea",
    "курганская область": "kurgan-area",
    "курская область": "kursk-area",
    "ленинградская область": "leningrad-region",
    "липецкая область": "lipetsk-area",
    "луганская народная республика": "republic-lugansk",
    "магаданская область": "magadan-area",
    "марий эл республика": "republic-mari-el",
    "мордовия республика": "republic-mordovia",
    "московская область": "moscow-area",
    "мурманская область": "murmansk-area",
    "ненецкий автономный округ": "autonomous-area-nenets",
    "нижегородская область": "nizhny-novgorod-area",
    "новгородская область": "novgorod-area",
    "новосибирская область": "novosibirsk-area",
    "омская область": "omsk-area",
    "оренбургская область": "orenburg-area",
    "орловская область": "oryol-area",
    "пензенская область": "penza-area",
    "пермский край": "territory-perm",
    "приморский край": "territory-primorsky",
    "псковская область": "pskov-area",
    "ростовская область": "rostov-area",
    "рязанская область": "ryazan-area",
    "самарская область": "samara-area",
    "саратовская область": "saratov-area",
    "саха(якутия) республика": "republic-sakha-yakutia",
    "сахалинская область": "sakhalin-area",
    "свердловская область": "sverdlovsk-area",
    "северная осетия-алания республика": "republic-north-ossetia-alania",
    "смоленская область": "smolensk-area",
    "ставропольский край": "territory-stavropol",
    "тамбовская область": "tambov-area",
    "татарстан республика": "republic-tatarstan",
    "тверская область": "tver-area",
    "томская область": "tomsk-area",
    "тульская область": "tula-area",
    "тыва республика": "republic-tyva",
    "тюменская область": "tyumen-area",
    "удмуртия республика": "republic-udmurtia",
    "ульяновская область": "ulyanovsk-area",
    "хабаровский край": "territory-khabarovsk",
    "хакасия республика": "republic-khakassia",
    "ханты-мансийский автономный округ": "autonomous-area-khanty-mansi",
    "херсонская область": "kherson-region",
    "челябинская область": "chelyabinsk-area",
    "чеченская республика": "republic-chechen",
    "чувашская республика": "republic-chuvash",
    "чукотский автономный округ": "autonomous-area-chukotka",
    "ямало-ненецкий ао": "autonomous-area-yamalo-nenets",
    "ярославская область": "yaroslavl-area",
}

# Словарь станций
stations_dict = {
    "клин": "klin",
    "москва": "moscow",
    "калуга": "kaluga-A",
    "тверь": "tver",
    "быково": "bykovo",
    "внуково": "vnukovo",
    "волоколамск": "volokolamsk",
    "дмитров": "dmitrov",
    "домодедово": "domodedovo",
    "егорьевск": "egorevsk",
    "каширa": "kashira",
    "коломна": "kolomna",
    "можайск": "mozhaysk",
    "москва вднх": "moscow",
    "москва балчуг": "moskva-balchug",
    "наро-фоминск": "naro-fominsk",
    "немчиновка": "nemchinovka",
    "ново-иерусалим": "novo-jerusalim",
    "орехово-зуево": "orekhovo-zuevo",
    "павловский посад": "pavlovsky-posad",
    "павловское": "pavlovskoe",
    "сергиев посад": "sergiev-posad",
    "серпухов": "serpukhov",
    "третьяково": "tretyakovo",
    "черусти": "cherusti",
    "шереметьево": "sheremetyevo",
    "железногорск": "zheleznogorsk",
    "курск": "kursk",
    "курчатов": "kurchatov",
    "обоянь": "oboyan",
    "поныри": "ponyri",
    "рыльск": "rylsk",
    "тим": "tim",
    "майкоп": "majkop",
    "горно-алтайск": "gorno-altaysk",
    "барнаул": "barnaul",
    "благовещенск": "blagoveshchensk",
    "архангельск": "arkhangelsk",
    "астрахань": "astrakhan",
    "уфа": "ufa",
    "белгород": "belgorod",
    "брянск": "bryansk",
    "улан-удэ": "ulan-ude",
    "владимир": "vladimir",
    "волгоград": "volgograd",
    "вологда": "vologda",
    "воронеж": "voronezh",
    "махачкала": "makhachkala",
    "донецк": "donetsk",
    "биробиджан": "birobidzhan",
    "чита": "chita",
    "бердянск": "berdyansk",
    "иваново": "ivanovo",
    "назарян": "nazran",
    "иркутск": "irkutsk",
    "нальчик": "nalchik",
    "калининград": "kaliningrad",
    "элиста": "elista",
    "петропавловск": "petropavlovsk",
    "черкесск": "cherkessk",
    "петрозаводск": "petrozavodsk",
    "кемерово": "kemerovo",
    "киров": "kirov",
    "сыктывкар": "syktyvkar",
    "кострома": "kostroma",
    "краснодар": "krasnodar",
    "красноярск": "krasnoyarsk",
    "симферополь": "simferopol",
    "курган": "kurgan",
    "липецк": "lipetsk",
    "луганск": "luhansk",
    "магадан": "magadan",
    "йошкар-ола": "joskar-ola",
    "саранск": "saransk",
    "мурманск": "murmansk",
    "нарьян-мар": "naryan-mar",
    "нижний новгород": "nizhny-novgorod",
    "новгород": "novgorod",
    "новосибирск": "novosibirsk",
    "омск": "omsk",
    "оренбург": "orenburg",
    "орёл": "orel",
    "пенза": "penza",
    "пермь": "perm",
    "владивосток": "vladivostok",
    "псков": "pskov",
    "ростов-на-дону": "rostov-na-donu",
    "рязань": "ryazan",
    "самара": "samara",
    "саратов": "saratov",
    "якутск": "yakutsk",
    "южно-сахалинск": "yuzhno-sakhalinsk",
    "екатеринбург": "yekaterinburg",
    "владикавказ": "vladikavkaz",
    "смоленск": "smolensk",
    "ставрополь": "stavropol",
    "тамбов": "tambov",
    "казань": "kazan",
    "абакан": "abakan",
    "тюмень": "tyumen",
    "ижевск": "izhevsk",
    "ульяновск": "ulyanovsk",
    "хабаровск": "khabarovsk",
    "грозный": "grozny",
    "чебоксары": "cheboksary",
    "анадырь": "anadyr",
    "салехард": "salehard",
    "вязьма": "vyazma",
    "гагарин": "gagarin",
    "рославль": "roslavl",
    "смоленск": "smolensk",
    "жердевка": "zerdevka",
    "кирсанов": "kirsanov",
    "мичуринск": "michurinsk",
    "моршанск": "morshansk",
    "обловка": "oblovka",
    "совхоз им.ленина": "sovkhoz_im_len",
    "тамбов амсг": "tambov",
    "анапа": "anapa",
    "армавир": "armavir",
    "белая глина": "belaya_glina",
    "геленджик": "gelendzhik",
    "горячий ключ": "goryachiy_klyuch",
    "джубга": "dzhubga",
    "должанская": "dolzhanskaya",
    "ейск": "eysk",
    "каневская": "kanevskaya",
    "красная поляна": "krasnaya_polyana",
    "краснодар": "krasnodar",
    "кропоткин": "kropotkin",
    "крымск": "krymsk",
    "кубанская": "kubanskaya",
    "кущевская": "kushchevskaya",
    "новороссийск": "novorossiysk",
    "приморско-ахтарск": "primorsko_akhtarsk",
    "славянск-на-кубани": "slavyansk_na_kubani",
    "сочи": "sochi_adler",
    "тамань": "tamany",
    "тихорецк": "tikhoretsk",
    "туапсе": "tuapse",
    "усть-лабинск": "ust_labinsk",
    "белогорка": "belogorka",
    "винницы": "vinnitsy",
    "вознесенье": "voznesenye",
    "волосово": "volosovo",
    "выборг": "vyborg",
    "ефимовская": "efimovskaya",
    "кингисепп": "kingisepp",
    "кириши": "kirishi",
    "лодейное поле": "lodeynoye_pole",
    "луга": "luga",
    "николаевская": "nikolaevskaya",
    "новая ладога": "novaya_ladoga",
    "озерки": "ozerki",
    "петрокрепость": "petrokrepost",
    "приозерск": "priozersk",
    "санкт-петербург": "sankt_peterburg",
    "сосново": "sosnovo",
    "тихвин": "tikhvin",
    "переславль-залесский": "pereslavl_zalesskiy",
    "пошехонье": "poshekhonye",
    "ростов": "rostov",
    "рыбинск": "rybinsk",
    "ярославль": "yaroslavl",
    "волово": "volovo",
    "ефремов": "efremov",
    "новомосковск": "novomoskovsk",
    "тула": "tula",
    "анна": "anna",
    "богучар": "boguchar",
    "борисоглебск": "borisoglebsk",
    "воронеж": "voronezh_1",
    "калач": "kalach",
    "лиски": "liski",
    "павловск": "pavlovsk",
    "арзамас": "arzamas",
    "ветлуга": "vetluga",
    "воскресенское": "voskresenskoe",
    "выкса": "vyksa",
    "городец волжская гмо": "gorodets_volzhskaya_gmo",
    "красные баки": "krasnye_baki",
    "лукоянов": "lukoyanov",
    "лысково": "lyskovo",
    "нижний новгород-1": "nizhny_novgorod",
    "павлово": "pavlovo",
    "сергач": "sergach",
    "шахунья": "shakhunya",
    "алапаевск": "alapaevsk",
    "артемовский": "artemovsky",
    "бисерть": "biserte",
    "верхнее дуброво": "verhnee_dubrovo",
    "верхотурье": "verhoturye",
    "висим": "visim",
    "гари": "gari",
    "екатеринбург": "ekaterinburg",
    "ивдель": "ivdel",
    "ирбит-фомино": "irbit_fomino",
    "каменск-уральский": "kamensk_uralsky",
    "камышлов": "kamyshlov",
    "кольцово": "kolcovo",
    "красноуфимск": "krasnoufimsk",
    "кушва": "kushva",
    "кытлым": "kytlym",
    "михайловск": "mihaylovsk",
    "невьянск": "nev'yansk",
    "нижний тагил": "nizhny_tagil",
    "понил": "ponil",
    "ревда": "revda",
    "североуральск": "severouralsk",
    "серов": "serov",
    "сысерть": "sysert",
    "таборы": "tabory",
    "тавда": "tavda",
    "тугулым": "tugulym",
    "туринск": "turinsk",
    "шамары": "shamary",
    "волгоград": "volgograd",
    "волжский": "volzhsky",
    "даниловка": "danilovka",
    "елань": "elan",
    "иловля": "ilovlya",
    "камышин": "kamyshin",
    "михайловка": "mihailovka",
    "нижний чир": "nizhny_chir",
    "паласовка": "pallasovka",
    "серафимович": "serafimovich",
    "урюпинск": "uryupinsk",
    "фролово": "frolovo",
    "эльтон": "elton",
    "большие кайбицы": "bolshie_kaybitsy",
    "бугульма": "bugulma",
    "елабуга": "elabuga",
    "казань": "kazan",
    "лаишево": "laishevo",
    "муслюмово": "muslyumovo_1",
    "набережные челны": "naberezhnye_chelny",
    "тетюши": "tetyushi",
    "чистополь": "chistopol",
    "чистополь": "chistopol_b",
    "чулпаново": "chulpanovo"
}

@bot.message_handler(commands=['stations'])
def send_weather_stations(message):
    bot.send_message(message.chat.id, "Введите регион (например, Московская область):")
    bot.register_next_step_handler(message, get_region)

# Функция для обработки ввода региона
def get_region(message):
    region_name = message.text.lower().strip()
    
    if region_name not in regions_dict:
        bot.send_message(message.chat.id, "Указанный регион не найден. Проверьте правильность ввода.")
        return
    
    region_code = regions_dict[region_name]
    bot.send_message(message.chat.id, "Введите название станции (например, Клин):")
    bot.register_next_step_handler(message, get_station, region=region_code)

# Функция для обработки ввода станции и парсинга данных
def get_station(message, region):
    station_name = message.text.lower().strip()

    if station_name not in stations_dict:
        bot.send_message(message.chat.id, "Указанная станция не найдена. Проверьте правильность ввода.")
        return
    
    # Получаем код станции
    station_code = stations_dict[station_name]
    
    # Формируем URL для региона и станции
    url = f"https://meteoinfo.ru/pogoda/russia/{region}/{station_code}"

    try:
        # Делаем запрос к сайту
        response = requests.get(url)
        
        # Проверяем статус ответа
        if response.status_code != 200:
            bot.send_message(message.chat.id, "Не удалось получить данные с сайта. Проверьте название региона и станции.")
            return

        # Парсим страницу
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Получаем время обновления данных
        update_time = soup.find("td", {"colspan": "2", "align": "right"})
        update_time = update_time.text.strip() if update_time else "Нет данных о времени обновления"
        
        # Находим таблицу с данными о погоде
        table = soup.find("table", {"border": "0", "style": "width:100%"})
        if not table:
            bot.send_message(message.chat.id, "Не удалось найти данные о погоде для указанной станции.")
            return

        # Словарь для хранения данных о погоде
        weather_data = {}

        # Парсим строки таблицы
        rows = table.find_all("tr")
        for row in rows:
            columns = row.find_all("td")
            if len(columns) == 2:
                parameter = columns[0].text.strip()  # Название параметра
                value = columns[1].text.strip()  # Значение параметра
                weather_data[parameter] = value

        # Формируем сообщение с данными о погоде
        message_text = f"📍 Погода для станции: {station_name.capitalize()}\n\n"
        message_text += f"🕒 Обновлено: {update_time}\n\n"
        message_text += f"🌡️ Температура воздуха: {weather_data.get('Температура воздуха, °C', 'Нет данных')} °C\n"
        message_text += f"🌡️ Минимальная температура: {weather_data.get('Минимальная температура, °C', 'Нет данных')} °C\n"
        message_text += f"💨 Средняя скорость ветра: {weather_data.get('Средняя скорость ветра, м/с', 'Нет данных')} м/с\n"
        message_text += f"➡️ Направление ветра: {weather_data.get('Направление ветра', 'Нет данных')}\n"
        message_text += f"🔽 Атмосферное давление: {weather_data.get('Атмосферное давление на уровне станции, мм рт.ст.', 'Нет данных')} мм рт.ст.\n"
        message_text += f"💧 Относительная влажность: {weather_data.get('Относительная влажность, %', 'Нет данных')} %\n"
        message_text += f"🌫️ Горизонтальная видимость: {weather_data.get('Горизонтальная видимость, км', 'Нет данных')} км\n"
        message_text += f"☁️ Балл общей облачности: {weather_data.get('Балл общей облачности', 'Нет данных')}\n"
        message_text += f"🌨️ Осадки за 12 часов: {weather_data.get('Осадки за 12 часов, мм', 'Нет данных')} мм\n"
        message_text += f"❄️ Высота снежного покрова: {weather_data.get('Высота снежного покрова, см', 'Нет данных')} см\n\n"
        message_text += "Данные предоставлены Гидрометцентром России"

        # Отправляем сообщение с погодными данными пользователю
        bot.send_message(message.chat.id, message_text)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при обработке данных: {str(e)}")
# echo-функция для станций meteoinfo.ru

@bot.message_handler(commands=['support'])
def get_support(message):
    bot.send_message(message.from_user.id, '🛠️ Для связи с техподдержкой напишите на нашу электронную почту: pogoda.radar@inbox.ru')
# echo-функция, которая отвечает за техподдержку бота

@bot.message_handler(content_types=['text'])
def error_404(message):
    bot.send_message(message.from_user.id, 'Неизвестная команда. Воспользуйтесь командой /help.')

keep_alive()#запускаем flask-сервер
def start_bot():
  while True:
    try:
        bot.polling(none_stop=True, interval=0) #запуск бота
    except Exception as e:
        print(f"Ошибка в работе бота! {str(e)}")

start_bot()
