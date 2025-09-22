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


def get_user_profile_by_tg_id(tg_id, link):
    params = {
        'filters[tg_id][$eq]': str(tg_id)
    }
    response = requests.get(f'{link}/api/user-profiles', params=params)
    response.raise_for_status()
    data = response.json().get('data') or []
    return data[0] if data else None


def create_user_profile(tg_id, link, email=None):
    payload = {'data': {'tg_id': str(tg_id)}}
    if email is not None:
        payload['data']['email'] = email
    response = requests.post(f'{link}/api/user-profiles', json=payload)
    try:
        response.raise_for_status()
        return response.json()['data']
    except requests.HTTPError:
        if response.status_code == 400:
            existing = get_user_profile_by_tg_id(tg_id)
            if existing:
                return existing
        raise


def get_cart_by_tg_id(tg_id, link):
    params = {
        'filters[tg_id][$eq]': str(tg_id)
    }
    resposne = requests.get(f'{link}/api/carts', params=params)
    resposne.raise_for_status()
    data = resposne.json().get('data') or []
    return data[0] if data else None


def create_cart_for_user(tg_id, link):
    payload = {'data': {'tg_id': str(tg_id)}}
    response = requests.post(f'{link}/api/carts', json=payload)
    try:
        response.raise_for_status()
        return response.json()['data']
    except requests.HTTPError:
        if response.status_code == 400:
            existing = get_cart_by_tg_id(tg_id, link)
            if existing:
                return existing
        raise
