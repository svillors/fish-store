import os
from io import BytesIO

import redis
import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from utils import (
    create_cart_view, get_or_create_cart, get_or_create_user_profile,
    fetch_product_items, send_menu
)


_database = redis.Redis(host='localhost', port=6379, db=0)


def start(update, context):
    send_menu(update, link)
    return "HANDLE_MENU"


def handle_menu(update, context):
    query = update.callback_query
    query.answer()
    query.message.delete()
    callback_data = query.data
    tg_id = update.effective_user.id

    if callback_data == 'mycart':
        cart_doc_id = get_or_create_cart(tg_id, link)
        raw_items = fetch_product_items(cart_doc_id, link)

        if not raw_items:
            text = 'Ваша корзина пуста'
            markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton('Назад', callback_data='back')]])
            query.message.reply_text(text=text, reply_markup=markup)
            return 'HANDLE_CART'

        lines, product_items = raw_items
        text, markup = create_cart_view(lines, product_items)
        query.message.reply_text(text=text, reply_markup=markup)
        return 'HANDLE_CART'

    elif callback_data.startswith('prod'):
        product_id = callback_data.split('-')[1]
        response = requests.get(
            f'{link}/api/products/{product_id}',
            params={'populate': 'picture'}
        )
        response.raise_for_status()
        response = response.json()

        image_url = response['data']['picture']['formats']['thumbnail']['url']
        image_response = requests.get(f'{link}{image_url}')
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
                    callback_data=f'add-{product_id}'
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
    return 'HANDLE_MENU'


def handle_product(update, context):
    query = update.callback_query

    if query.data == 'back':
        context.user_data.clear()
        query.message.delete()
        send_menu(update, link)
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
            f'{link}/api/carts',
            params=params
        )
        response.raise_for_status()
        response = response.json()

        cart_doc_id = get_or_create_cart(tg_id, link)

        payload = {'data': {
            'product': product_doc_id,
            'cart': cart_doc_id,
            'quantity': float(quantity)
        }}
        response = requests.post(
            f'{link}/api/product-items',
            json=payload
        )
        response.raise_for_status()

        context.user_data.clear()
        query.message.delete()
        send_menu(update, link)
        return 'HANDLE_MENU'
    else:
        query.answer('чтобы добвить товар в корзину нужно выбрать количество')
        return 'HANDLE_PRODUCT'


def handle_cart(update, context):
    query = update.callback_query
    query.answer()
    query.message.delete()
    callback_data = query.data
    tg_id = update.effective_user.id

    if callback_data == "back":
        send_menu(update, link)
        return 'HANDLE_MENU'

    elif callback_data.startswith('del'):
        prod_item_doc_id = callback_data.split('-')[1]
        response = requests.delete(
            f'{link}/api/product-items/{prod_item_doc_id}')
        response.raise_for_status()
        cart_doc_id = get_or_create_cart(tg_id, link)
        raw_items = fetch_product_items(cart_doc_id, link)

        if not raw_items:
            text = 'Ваша корзина пуста'
            markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton('Назад', callback_data='back')]])
            query.message.reply_text(text=text, reply_markup=markup)
            return 'HANDLE_CART'

        lines, product_items = raw_items
        text, markup = create_cart_view(lines, product_items)
        query.message.reply_text(text=text, reply_markup=markup)

        return 'HANDLE_CART'

    elif callback_data == 'buy':
        query.message.reply_text(text='Напишите вашу почту')
        return 'WAITING_EMAIL'


def waiting_email(update, context):
    text = update.message.text
    tg_id = update.effective_user.id
    doc_id = get_or_create_user_profile(tg_id, link)
    payload = {'data': {'email': text}}
    response = requests.put(
        f'{link}/api/user-profiles/{doc_id}',
        json=payload
    )
    response.raise_for_status()
    send_menu(update)
    return 'HANDLE_MENU'


def handle_users_reply(update, context):
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
        'HANDLE_PRODUCT': handle_product,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': waiting_email
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
    link = os.getenv("STRAPI_URL", 'http://localhost:1337')
    token = os.environ["TELEGRAM_TOKEN"]
    db = get_database_connection()
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()
    updater.idle()
