# Fish store
A simple Telegram bot for a seafood store. Users can browse products, pick a quantity, add items to the cart and order.

## Requirements
- This bot uses CMS Strapi. You should install it by following this [guide](https://docs.strapi.io/cms/installation).
- This bot uses Redis to store user state. [Install Redis](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/)
- Install python dependencies using:
```bash
pip install -r requirements.txt
```

## Environment
### Environment variables
- TELEGRAM_TOKEN - your telegram bot's token. Required.
- STRAPI_URL - url to strapi (default: http://localhost:1337)
- DATABASE_HOST - redis host
- DATABASE_PORT - redis port
- DATABASE_PASSWORD - redis password
### Strapi content types
- Product: name (text), description (text), price (number), picture (media)
- Cart: tg_id (text), relation one-to-many with Product-item
- Product-item: quantity (number), relations: many-to-one product, many-to-one cart
- User-profile : tg_id (text), email (text)

## Run
Start Redis and Strapi, then:
```bash
python3 bot.py
```
