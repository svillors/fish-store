import os
from io import BytesIO

import redis
import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler


_database = redis.Redis(host='localhost', port=6379, db=0)


def send_menu(update):
    response = requests.get('http://localhost:1337/api/products')
    response.raise_for_status()
    keyboard = []
    for product in response.json()['data']:
        keyboard.append(
            [InlineKeyboardButton(
                product['name'], callback_data=product['documentId']
            )]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = update.message or update.callback_query.message

    message.reply_text(text='Выберите товар', reply_markup=reply_markup)


def start(update, context):
    send_menu(update)
    return "HANDLE_MENU"


def handle_menu(update, context):
    query = update.callback_query
    query.answer()
    callback_data = query.data

    response = requests.get(
        f'http://localhost:1337/api/products/{callback_data}',
        params={'populate': 'picture'}
    )
    response.raise_for_status()
    response = response.json()

    image_url = response['data']['picture']['formats']['thumbnail']['url']
    image_response = requests.get(f'http://localhost:1337{image_url}')
    image_response.raise_for_status()
    image = BytesIO(image_response.content)

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton('Назад', callback_data='back')]]
    )

    query.message.delete()
    query.message.reply_photo(
        photo=InputFile(image),
        caption=response['data']['description'],
        reply_markup=markup
    )

    return 'HANDLE_DESCRIPTION'


def handle_description(update, context):
    query = update.callback_query
    query.answer()
    query.message.delete()

    send_menu(update)
    return 'HANDLE_MENU'


def handle_users_reply(update, context):
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description
    }
    state_handler = states_functions[user_state]
    next_state = state_handler(update, context)
    db.set(chat_id, next_state)


def get_database_connection():
    global _database
    if _database is None:
        database_password = os.getenv("DATABASE_PASSWORD")
        database_host = os.getenv("DATABASE_HOST")
        database_port = os.getenv("DATABASE_PORT")
        _database = redis.Redis(host=database_host, port=database_port, password=database_password)
    return _database


if __name__ == '__main__':
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN")
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()
    updater.idle()
