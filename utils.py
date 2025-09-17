import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def send_menu(update, link):
    response = requests.get(f'{link}/api/products')
    response.raise_for_status()
    keyboard = []
    for product in response.json()['data']:
        keyboard.append(
            [InlineKeyboardButton(
                product['name'],
                callback_data=f'prod-{product["documentId"]}'
            )]
        )

    keyboard.append(
        [InlineKeyboardButton('Моя корзина', callback_data='mycart')]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = update.message or update.callback_query.message

    message.reply_text(text='Выберите товар', reply_markup=reply_markup)


def fetch_product_items(cart_doc_id, link):
    params = {
        'filters[cart][documentId][$eq]': cart_doc_id,
        'populate': 'product'
    }
    response = requests.get(f'{link}/api/product-items', params=params)
    response.raise_for_status()
    response = response.json()
    if not response.get('data', None):
        return
    lines = []
    product_items = []
    for item in response['data']:
        quantity = int(item['quantity'])
        product = item['product']
        name = product['name']
        product_items.append((item['documentId'], name))
        price = int(product['price'])
        cost = price * quantity
        line = f'• {name}: \nКол-во: {quantity} кг.\nОбщ. цена: {cost} р.'
        lines.append(line)

    return (lines, product_items)


def create_cart_view(lines, product_items):
    keyboard = []
    for item in product_items:
        doc_id, name = item
        keyboard.append(
            [InlineKeyboardButton(
                f'Убрать товар: {name}', callback_data=f'del-{doc_id}'
            )]
        )
    keyboard.append([InlineKeyboardButton('Оплата', callback_data='buy')])
    keyboard.append([InlineKeyboardButton('Назад', callback_data='back')])
    keyboard_markup = InlineKeyboardMarkup(keyboard)
    return ('Ваша Корзина:\n\n' + '\n\n'.join(lines), keyboard_markup)


def get_or_create_cart(tg_id, link):
    params = {
        'filters[tg_id][$eq]': tg_id,
    }
    response = requests.get(
        f'{link}/api/carts',
        params=params
    )
    response.raise_for_status()
    response = response.json()

    if response['data']:
        return response['data'][0]['documentId']

    payload = {'data': {'tg_id': str(tg_id)}}
    response = requests.post(
        f'{link}/api/carts',
        json=payload
    )
    response.raise_for_status()
    return response.json()['data']['documentId']


def get_or_create_user_profile(tg_id, link):
    params = {
        'filters[tg_id][$eq]': tg_id,
    }
    response = requests.get(
        f'{link}/api/user-profiles',
        params=params
    )
    response.raise_for_status()
    response = response.json()

    if response['data']:
        return response['data'][0]['documentId']

    payload = {'data': {'tg_id': str(tg_id)}}
    response = requests.post(
        f'{link}/api/user-profiles',
        json=payload
    )
    response.raise_for_status()
    return response.json()['data']['documentId']