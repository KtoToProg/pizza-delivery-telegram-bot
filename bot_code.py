import telebot
from telebot import types
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import os
import time

# --- Настройки Google Sheets ---
SPREADSHEET_ID = '1i2k6_RWZB1VCsiYxmuy8pig9yB65OMJrhqaAjMfPImM'
CREDENTIALS_FILE = 'credentials.json'
BACKUP_FILE = 'orders_backup.json'

def init_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1

def write_order_to_sheet(sheet, user_name, pizza, size, quantity, address, phone):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [now, user_name, pizza, size, quantity, address, phone]
    sheet.append_row(row)

def write_order_with_retry(sheet, order_data, max_retries=3, delay=5):
    for attempt in range(1, max_retries + 1):
        try:
            write_order_to_sheet(
                sheet,
                order_data['user_name'],
                order_data['pizza'],
                order_data['size'],
                order_data['quantity'],
                order_data['address'],
                order_data['phone']
            )
            print(f"✅ Заказ {order_data['pizza']} записан в таблицу (попытка {attempt})")
            return True
        except Exception as e:
            print(f"⚠️ Попытка {attempt} записи не удалась: {e}")
            if attempt < max_retries:
                print(f"⏳ Повтор через {delay} секунд...")
                time.sleep(delay)
    return False

def save_order_backup(order_data):
    orders = []
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                orders = json.load(f)
        except (json.JSONDecodeError, IOError):
            orders = []
    orders.append(order_data)
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)
    print(f"📦 Заказ {order_data['pizza']} сохранён в резервный файл")

def retry_failed_orders():
    if not os.path.exists(BACKUP_FILE):
        return
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            orders = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    if not orders:
        return
    print(f"📦 Найдено {len(orders)} неотправленных заказов. Пытаемся отправить...")
    remaining = []
    for idx, order in enumerate(orders, 1):
        print(f"⏳ Обработка заказа #{idx}...")
        if sheet is not None:
            success = write_order_with_retry(sheet, order, max_retries=2, delay=3)
            if success:
                print(f"✅ Резервный заказ #{idx} отправлен")
            else:
                print(f"❌ Резервный заказ #{idx} не удалось отправить, оставляем в резерве")
                remaining.append(order)
        else:
            remaining.append(order)
    if remaining:
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining, f, ensure_ascii=False, indent=2)
        print(f"⚠️ {len(remaining)} заказов остались в резервном файле")
    else:
        if os.path.exists(BACKUP_FILE):
            os.remove(BACKUP_FILE)
            print("🗑️ Резервный файл очищен (все заказы отправлены)")

ADMIN_CHAT_ID = 5544677633

# ============================================================
# Cloudflare Worker как прокси для Telegram API
# ============================================================
TELEGRAM_API_PROXY_URL = "https://rapid-bar-672d.kto696876.workers.dev"

# Перенаправляем ВСЕ запросы бота через Cloudflare Worker
telebot.apihelper.API_URL = f"{TELEGRAM_API_PROXY_URL}/bot{{0}}/{{1}}"

telebot.apihelper.READ_TIMEOUT = 60

bot = telebot.TeleBot('8403327210:AAFZVWCHvrhIRq050DJTzxyJ7XmPzUA4CUw')

# Инициализация Google Sheets
try:
    sheet = init_google_sheets()
    print("✅ Подключение к Google Sheets успешно")
    retry_failed_orders()
except Exception as e:
    print(f"❌ Ошибка подключения к Google Sheets: {e}")
    sheet = None

# ============================================================
# i18n: данные переводов
# ============================================================
DEFAULT_LANG = 'ru'

PIZZAS = {
    'margherita': {'ru': 'Маргарита', 'en': 'Margherita'},
    'pepperoni':  {'ru': 'Пепперони', 'en': 'Pepperoni'},
    'hawaiian':   {'ru': 'Гавайская', 'en': 'Hawaiian'},
}

SIZES = {
    's': {'ru': '25см', 'en': '25cm'},
    'm': {'ru': '30см', 'en': '30cm'},
    'l': {'ru': '35см', 'en': '35cm'},
}

TRANSLATIONS = {
    'ru': {
        'greeting': "Привет - привет, {name}!\nВыберите пиццу:",
        'choose_pizza': "Выберите пиццу:",
        'chosen_pizza': "Вы выбрали {pizza}.\nТеперь выберите размер:",
        'size_small': "Маленькая {size}",
        'size_medium': "Средняя {size}",
        'size_large': "Большая {size}",
        'back': "🔙 Назад",
        'back_to_size': "🔙 Назад к выбору размера",
        'back_to_quantity': "🔙 Назад к количеству",
        'back_to_address': "🔙 Назад к адресу",
        'back_to_phone': "🔙 Назад к телефону",
        'confirm': "✅ Подтвердить",
        'cancel': "❌ Отменить",
        'ask_quantity': "Вы выбрали {pizza} размер {size}.\nТеперь введите количество (целое число > 0):",
        'ask_quantity_again': "Вы выбрали {pizza} размер {size}.\nТекущее количество: {qty}\nВведите новое количество (целое число > 0):",
        'ask_address': "Вы выбрали {pizza} размер {size}, количество {qty}.\nВведите адрес доставки:",
        'ask_phone': "Вы выбрали {pizza} размер {size}, количество {qty}, адрес {address}.\nВведите номер телефона:",
        'qty_ok': "Количество: {qty}.\nТеперь введите адрес доставки:",
        'address_ok': "Адрес: {address}.\nТеперь введите номер телефона:",
        'qty_err_positive': "❌ Количество должно быть больше 0. Попробуйте ещё раз:",
        'qty_err_nan': "❌ Это не число. Введите целое положительное число:",
        'address_err_short': "❌ Адрес слишком короткий. Введите полный адрес (минимум 6 символов):",
        'phone_err': "❌ Неверный формат телефона. Введите номер (только цифры, возможно с + в начале, от 10 до 15 символов):",
        'order_check': ("📋 Проверьте ваш заказ:\n\n"
                        "Пицца: {pizza}\n"
                        "Размер: {size}\n"
                        "Количество: {qty}\n"
                        "Адрес: {address}\n"
                        "Телефон: {phone}\n\n"
                        "Всё верно? Подтвердите или отмените заказ."),
        'order_accepted': "✅ Спасибо! Ваш заказ принят.",
        'order_admin_issue': " Но возникла проблема с уведомлением администратора. Мы скоро свяжемся с вами.",
        'order_sheet_issue': " Ваш заказ сохранён, но возможна небольшая задержка в обработке. Администратор свяжется с вами.",
        'order_missing_data': "❌ Ошибка: не хватает данных для оформления заказа. Начните заказ сначала /start",
        'order_cancelled': "❌ Заказ отменён.\nВы можете начать заново командой /start",
        'use_buttons': "Пожалуйста, используйте кнопки для выбора.",
        'language_selection': "🌐 Выберите язык / Choose language:",
        'language_changed': "✅ Язык изменён на русский.",
    },
    'en': {
        'greeting': "Hello, {name}!\nChoose a pizza:",
        'choose_pizza': "Choose a pizza:",
        'chosen_pizza': "You chose {pizza}.\nNow choose the size:",
        'size_small': "Small {size}",
        'size_medium': "Medium {size}",
        'size_large': "Large {size}",
        'back': "🔙 Back",
        'back_to_size': "🔙 Back to size selection",
        'back_to_quantity': "🔙 Back to quantity",
        'back_to_address': "🔙 Back to address",
        'back_to_phone': "🔙 Back to phone",
        'confirm': "✅ Confirm",
        'cancel': "❌ Cancel",
        'ask_quantity': "You chose {pizza}, size {size}.\nNow enter the quantity (integer > 0):",
        'ask_quantity_again': "You chose {pizza}, size {size}.\nCurrent quantity: {qty}\nEnter new quantity (integer > 0):",
        'ask_address': "You chose {pizza}, size {size}, quantity {qty}.\nEnter the delivery address:",
        'ask_phone': "You chose {pizza}, size {size}, quantity {qty}, address {address}.\nEnter your phone number:",
        'qty_ok': "Quantity: {qty}.\nNow enter the delivery address:",
        'address_ok': "Address: {address}.\nNow enter the phone number:",
        'qty_err_positive': "❌ Quantity must be greater than 0. Please try again:",
        'qty_err_nan': "❌ That is not a number. Please enter a positive integer:",
        'address_err_short': "❌ Address is too short. Please enter the full address (at least 6 characters):",
        'phone_err': "❌ Invalid phone format. Please enter a number (digits only, optionally starting with +, 10 to 15 characters):",
        'order_check': ("📋 Please check your order:\n\n"
                        "Pizza: {pizza}\n"
                        "Size: {size}\n"
                        "Quantity: {qty}\n"
                        "Address: {address}\n"
                        "Phone: {phone}\n\n"
                        "Is everything correct? Confirm or cancel the order."),
        'order_accepted': "✅ Thank you! Your order has been accepted.",
        'order_admin_issue': " However, there was a problem notifying the administrator. We will contact you soon.",
        'order_sheet_issue': " Your order has been saved, but there may be a slight delay in processing. The administrator will contact you.",
        'order_missing_data': "❌ Error: insufficient data to place the order. Please start over with /start",
        'order_cancelled': "❌ Order cancelled.\nYou can start over with the /start command",
        'use_buttons': "Please use the buttons to make a selection.",
        'language_selection': "🌐 Выберите язык / Choose language:",
        'language_changed': "✅ Language changed to English.",
    },
}

# Глобальные словари
user_language = {}
user_data = {}
user_state = {}

def get_lang(chat_id):
    return user_language.get(chat_id, DEFAULT_LANG)

def t(chat_id, key, **kwargs):
    lang = get_lang(chat_id)
    text = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, key)
    return text.format(**kwargs) if kwargs else text

def pizza_label(pizza_key, chat_id):
    return PIZZAS.get(pizza_key, {}).get(get_lang(chat_id), pizza_key)

def size_label(size_key, chat_id):
    return SIZES.get(size_key, {}).get(get_lang(chat_id), size_key)


# ---------- Клавиатуры ----------
def get_language_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
    btn_en = types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    keyboard.add(btn_ru, btn_en)
    return keyboard

def get_pizza_keyboard(chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for key in PIZZAS:
        buttons.append(types.InlineKeyboardButton(
            f"🍕{pizza_label(key, chat_id)}🍕",
            callback_data=f"pizza_{key}"
        ))
    keyboard.add(*buttons)
    return keyboard

def get_size_keyboard(pizza_key, chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    btn_s = types.InlineKeyboardButton(
        t(chat_id, 'size_small', size=size_label('s', chat_id)),
        callback_data=f"{pizza_key}_size_s")
    btn_m = types.InlineKeyboardButton(
        t(chat_id, 'size_medium', size=size_label('m', chat_id)),
        callback_data=f"{pizza_key}_size_m")
    btn_l = types.InlineKeyboardButton(
        t(chat_id, 'size_large', size=size_label('l', chat_id)),
        callback_data=f"{pizza_key}_size_l")
    btn_back = types.InlineKeyboardButton(t(chat_id, 'back'), callback_data="back_to_pizza")
    keyboard.add(btn_s, btn_m, btn_l)
    keyboard.add(btn_back)
    return keyboard

def get_back_to_size_keyboard(chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(t(chat_id, 'back_to_size'), callback_data="back_to_size"))
    return keyboard

def get_back_to_quantity_keyboard(chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(t(chat_id, 'back_to_quantity'), callback_data="back_to_quantity"))
    return keyboard

def get_back_to_address_keyboard(chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(t(chat_id, 'back_to_address'), callback_data="back_to_address"))
    return keyboard

def get_back_to_phone_keyboard(chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(t(chat_id, 'back_to_phone'), callback_data="back_to_phone"))
    return keyboard

def get_confirmation_keyboard(chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton(t(chat_id, 'confirm'), callback_data="confirm_order")
    btn_cancel = types.InlineKeyboardButton(t(chat_id, 'cancel'), callback_data="cancel_order")
    keyboard.add(btn_confirm, btn_cancel)
    return keyboard


# ---------- Хелперы для меню ----------
def send_language_selection(chat_id, edit_message_id=None):
    text = TRANSLATIONS['ru']['language_selection']  # bilingual
    if edit_message_id:
        bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id,
                              text=text, reply_markup=get_language_keyboard())
    else:
        bot.send_message(chat_id, text, reply_markup=get_language_keyboard())

def send_pizza_menu(chat_id, name, edit_message_id=None):
    text = t(chat_id, 'greeting', name=name) if name else t(chat_id, 'choose_pizza')
    if edit_message_id:
        bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id,
                              text=text, reply_markup=get_pizza_keyboard(chat_id))
    else:
        bot.send_message(chat_id, text, reply_markup=get_pizza_keyboard(chat_id))


# ---------- Команды ----------
@bot.message_handler(commands=['start', 'hello', 'привет'])
def main(message):
    chat_id = message.chat.id
    if chat_id not in user_language:
        send_language_selection(chat_id)
    else:
        send_pizza_menu(chat_id, message.from_user.first_name)

@bot.message_handler(commands=['language', 'lang', 'язык'])
def change_language(message):
    send_language_selection(message.chat.id)


# ---------- Обработчик нажатий ----------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    data = call.data
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    # --- Смена языка ---
    if data.startswith("lang_"):
        lang = data.replace("lang_", "")
        if lang in ('ru', 'en'):
            user_language[chat_id] = lang
            send_pizza_menu(chat_id, call.from_user.first_name, edit_message_id=msg_id)
        return

    # Назад к пицце
    if data == "back_to_pizza":
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=t(chat_id, 'choose_pizza'),
            reply_markup=get_pizza_keyboard(chat_id)
        )
        return

    # Выбор пиццы
    elif data.startswith("pizza_"):
        pizza_key = data.replace("pizza_", "")
        if pizza_key not in PIZZAS:
            return
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=t(chat_id, 'chosen_pizza', pizza=pizza_label(pizza_key, chat_id)),
            reply_markup=get_size_keyboard(pizza_key, chat_id)
        )
        return

    # Выбор размера
    elif "_size_" in data:
        pizza_key, size_key = data.split("_size_")
        user_data[chat_id] = {'pizza': pizza_key, 'size': size_key}
        user_state[chat_id] = 'waiting_quantity'
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=t(chat_id, 'ask_quantity',
                   pizza=pizza_label(pizza_key, chat_id),
                   size=size_label(size_key, chat_id)),
            reply_markup=get_back_to_size_keyboard(chat_id)
        )
        return

    # Назад к размеру
    elif data == "back_to_size":
        pizza_key = user_data.get(chat_id, {}).get('pizza', '')
        if pizza_key:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'chosen_pizza', pizza=pizza_label(pizza_key, chat_id)),
                reply_markup=get_size_keyboard(pizza_key, chat_id)
            )
            user_state[chat_id] = None
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'choose_pizza'),
                reply_markup=get_pizza_keyboard(chat_id)
            )
        return

    # Назад к количеству
    elif data == "back_to_quantity":
        pizza_key = user_data.get(chat_id, {}).get('pizza', '')
        size_key = user_data.get(chat_id, {}).get('size', '')
        if pizza_key and size_key:
            current_qty = user_data.get(chat_id, {}).get('quantity', '—')
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'ask_quantity_again',
                       pizza=pizza_label(pizza_key, chat_id),
                       size=size_label(size_key, chat_id),
                       qty=current_qty),
                reply_markup=get_back_to_size_keyboard(chat_id)
            )
            user_state[chat_id] = 'waiting_quantity'
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'choose_pizza'),
                reply_markup=get_pizza_keyboard(chat_id)
            )
        return

    # Назад к адресу
    elif data == "back_to_address":
        d = user_data.get(chat_id, {})
        pizza_key, size_key, qty = d.get('pizza'), d.get('size'), d.get('quantity')
        if pizza_key and size_key and qty:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'ask_address',
                       pizza=pizza_label(pizza_key, chat_id),
                       size=size_label(size_key, chat_id),
                       qty=qty),
                reply_markup=get_back_to_quantity_keyboard(chat_id)
            )
            user_state[chat_id] = 'waiting_address'
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'choose_pizza'),
                reply_markup=get_pizza_keyboard(chat_id)
            )
        return

    # Назад к телефону
    elif data == "back_to_phone":
        d = user_data.get(chat_id, {})
        pizza_key, size_key = d.get('pizza'), d.get('size')
        qty, address = d.get('quantity'), d.get('address')
        if pizza_key and size_key and qty and address:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'ask_phone',
                       pizza=pizza_label(pizza_key, chat_id),
                       size=size_label(size_key, chat_id),
                       qty=qty, address=address),
                reply_markup=get_back_to_address_keyboard(chat_id)
            )
            user_state[chat_id] = 'waiting_phone'
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'choose_pizza'),
                reply_markup=get_pizza_keyboard(chat_id)
            )
        return

    # Подтверждение заказа
    elif data == "confirm_order":
        d = user_data.get(chat_id, {})
        pizza_key = d.get('pizza')
        size_key = d.get('size')
        quantity = d.get('quantity')
        address = d.get('address')
        phone = d.get('phone')

        if pizza_key and size_key and quantity and address and phone:
            # Данные для Sheets остаются на русском (совместимость с уже накопленными строками)
            order_data = {
                'user_name': call.from_user.first_name or 'Аноним',
                'pizza': PIZZAS[pizza_key]['ru'],
                'size': SIZES[size_key]['ru'],
                'quantity': quantity,
                'address': address,
                'phone': phone
            }

            # --- 1. Уведомление админу (на английском + пометка языка клиента) ---
            admin_text = (
                f"<b>🆕 New order!</b>\n\n"
                f"🍕 Pizza: {PIZZAS[pizza_key]['en']}\n"
                f"📏 Size: {SIZES[size_key]['en']}\n"
                f"🔢 Quantity: {quantity}\n"
                f"📍 Address: {address}\n"
                f"📞 Phone: {phone}\n"
                f"🆔 User: {call.from_user.first_name} (@{call.from_user.username or 'none'})\n"
                f"🌐 Client language: {get_lang(chat_id).upper()}"
            )
            try:
                bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode='HTML')
                admin_ok = True
            except Exception as e:
                print(f"❌ Ошибка отправки админу: {e}")
                admin_ok = False

            # --- 2. Запись в Google Sheets ---
            if sheet is not None:
                success = write_order_with_retry(sheet, order_data, max_retries=3, delay=5)
                if success:
                    sheet_ok = True
                else:
                    save_order_backup(order_data)
                    sheet_ok = False
            else:
                save_order_backup(order_data)
                sheet_ok = False

            # --- 3. Сообщение пользователю ---
            user_text = t(chat_id, 'order_accepted')
            if not admin_ok:
                user_text += t(chat_id, 'order_admin_issue')
            if not sheet_ok:
                user_text += t(chat_id, 'order_sheet_issue')

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=user_text,
                reply_markup=None
            )

            # --- 4. Очистка ---
            if chat_id in user_data:
                del user_data[chat_id]
            user_state[chat_id] = None
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=t(chat_id, 'order_missing_data'),
                reply_markup=None
            )
            if chat_id in user_data:
                del user_data[chat_id]
            user_state[chat_id] = None
        return

    # Отмена заказа
    elif data == "cancel_order":
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=t(chat_id, 'order_cancelled'),
            reply_markup=None
        )
        if chat_id in user_data:
            del user_data[chat_id]
        user_state[chat_id] = None
        return


# ---------- Текстовые сообщения ----------
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    state = user_state.get(chat_id)

    if state == 'waiting_quantity':
        try:
            quantity = int(message.text.strip())
            if quantity > 0:
                user_data[chat_id]['quantity'] = quantity
                user_state[chat_id] = 'waiting_address'
                bot.send_message(
                    chat_id,
                    t(chat_id, 'qty_ok', qty=quantity),
                    reply_markup=get_back_to_quantity_keyboard(chat_id)
                )
            else:
                bot.send_message(chat_id, t(chat_id, 'qty_err_positive'))
        except ValueError:
            bot.send_message(chat_id, t(chat_id, 'qty_err_nan'))

    elif state == 'waiting_address':
        address = message.text.strip()
        if len(address) > 5:
            user_data[chat_id]['address'] = address
            user_state[chat_id] = 'waiting_phone'
            bot.send_message(
                chat_id,
                t(chat_id, 'address_ok', address=address),
                reply_markup=get_back_to_address_keyboard(chat_id)
            )
        else:
            bot.send_message(chat_id, t(chat_id, 'address_err_short'))

    elif state == 'waiting_phone':
        phone = message.text.strip()
        if re.match(r'^\+?\d{10,15}$', phone):
            user_data[chat_id]['phone'] = phone
            user_state[chat_id] = None
            d = user_data[chat_id]
            bot.send_message(
                chat_id,
                t(chat_id, 'order_check',
                  pizza=pizza_label(d['pizza'], chat_id),
                  size=size_label(d['size'], chat_id),
                  qty=d['quantity'],
                  address=d['address'],
                  phone=phone),
                reply_markup=get_confirmation_keyboard(chat_id)
            )
        else:
            bot.send_message(chat_id, t(chat_id, 'phone_err'))

    else:
        bot.send_message(chat_id, t(chat_id, 'use_buttons'))


# ---------- Запуск ----------
if __name__ == '__main__':
    print(f"🌐 Используем Cloudflare Worker: {TELEGRAM_API_PROXY_URL}")
    print(f"🔗 API URL: {telebot.apihelper.API_URL}")
    while True:
        try:
            print("Бот запущен. Ожидание обновлений...")
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Бот упал с ошибкой: {e}")
            print("Перезапуск через 5 секунд...")
            time.sleep(5)
