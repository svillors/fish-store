import os
from io import BytesIO

import redis
import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler


load_dotenv()
BASE_URL = 'http://localhost:1337' or os.getenv('STRAPI_URL')
_database = redis.Redis(host='localhost', port=6379, db=0)


def send_menu(update):
    response = requests.get(f'{BASE_URL}/api/products')
    response.raise_for_status()
    keyboard = []
    for product in response.json()['data']:
        keyboard.append(
            [InlineKeyboardButton(
                product['name'], callback_data=product['documentId']
            )]
        )

    keyboard.append(
        [InlineKeyboardButton('Моя корзина', callback_data='mycart')]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = update.message or update.callback_query.message

    message.reply_text(text='Выберите товар', reply_markup=reply_markup)


def fetch_product_items(cart_doc_id):
    params = {
        'filters[cart][documentId][$eq]': cart_doc_id,
        'populate': 'products'
    }
    response = requests.get(f'{BASE_URL}/api/product-items', params=params)
    response.raise_for_status()
    lines = []
    for item in response.json()['data']:
        quantity = int(item['quantity'])
        product = item['products'][0]
        name = product['name']
        price = int(product['price'])
        cost = price * quantity
        line = f'• {name}: \nКол-во: {quantity} кг.\nОбщ. цена: {cost} р.'
        lines.append(line)

    return 'Ваша корзина:\n\n' + '\n\n'.join(lines)


def get_or_create_cart(tg_id):
    params = {
        'filters[tg_id][$eq]': tg_id,
    }
    response = requests.get(
        f'{BASE_URL}/api/carts',
        params=params
    )
    response.raise_for_status()
    response = response.json()

    if response['data']:
        return response['data'][0]['documentId']

    payload = {'data': {'tg_id': str(tg_id)}}
    response = requests.post(
        f'{BASE_URL}/api/carts',
        json=payload
    )
    response.raise_for_status()
    return response.json()['data']['documentId']


def start(update, context):
    send_menu(update)
    return "HANDLE_MENU"


def handle_menu(update, context):
    query = update.callback_query
    query.answer()
    query.message.delete()
    callback_data = query.data
    tg_id = update.effective_user.id

    if callback_data == 'mycart':
        cart_doc_id = get_or_create_cart(tg_id)
        text = fetch_product_items(cart_doc_id)
        query.message.reply_text(text=text)
        return 'HANDLE_MENU'

    response = requests.get(
        f'{BASE_URL}/api/products/{callback_data}',
        params={'populate': 'picture'}
    )
    response.raise_for_status()
    response = response.json()

    image_url = response['data']['picture']['formats']['thumbnail']['url']
    image_response = requests.get(f'{BASE_URL}{image_url}')
    image_response.raise_for_status()
    image = BytesIO(image_response.content)

    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('5 кг.', callback_data='quantity-5'),
                InlineKeyboardButton('10 кг.', callback_data='quantity-10'),
                InlineKeyboardButton('15 кг.', callback_data='quantity-15')
            ],
            [InlineKeyboardButton(
                'Добавить в корзину',
                callback_data=f'add-{callback_data}'
            )],
            [InlineKeyboardButton('Назад', callback_data='back')]
        ]
    )

    query.message.reply_photo(
        photo=InputFile(image),
        caption=response['data']['description'],
        reply_markup=markup
    )

    return 'HANDLE_PRODUCT'


def handle_product(update, context):
    query = update.callback_query

    if query.data == 'back':
        context.user_data.clear()
        query.message.delete()
        send_menu(update)
        return 'HANDLE_MENU'

    elif query.data.startswith('quantity'):
        context.user_data['quantity'] = query.data.split('-')[1]
        return 'HANDLE_PRODUCT'

    elif query.data.startswith('add') and context.user_data.get('quantity', None):
        product_doc_id = query.data.split('-')[1]
        tg_id = update.effective_user.id
        quantity = context.user_data.get('quantity')

        params = {'filters[tg_id][$eq]': tg_id}
        response = requests.get(
            f'{BASE_URL}/api/carts',
            params=params
        )
        response.raise_for_status()
        response = response.json()

        cart_doc_id = get_or_create_cart(tg_id)

        payload = {'data': {
            'products': product_doc_id,
            'cart': cart_doc_id,
            'quantity': float(quantity)
        }}
        response = requests.post(
            f'{BASE_URL}/api/product-items',
            json=payload
        )
        response.raise_for_status()

        context.user_data.clear()
        query.message.delete()
        send_menu(update)
        return 'HANDLE_MENU'
    else:
        query.answer('чтобы добвить товар в корзину нужно выбрать количество')
        return 'HANDLE_PRODUCT'


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
        'HANDLE_PRODUCT': handle_product
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
    token = os.getenv("TELEGRAM_TOKEN")
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()
    updater.idle()
