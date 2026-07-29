import telebot
from telebot import types
import re
import html

ADMIN_CHAT_ID = "YOUR CHAT ID"

# Настройка прокси
telebot.apihelper.proxy = {"YOUR PROXY (IF TELEGRAM IS UNAVAILABLE IN YOUR REGION)"}

telebot.apihelper.READ_TIMEOUT = 60

bot = telebot.TeleBot('YOUR_TELEGRAM_TOKEN')

# Глобальные словари
user_data = {}
user_state = {}

size_names = {"s": "25см", "m": "30см", "l": "35см"}

# ---------- Клавиатуры ----------
def get_pizza_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🍕Маргарита🍕", callback_data="pizza_Маргарита")
    btn2 = types.InlineKeyboardButton("🍕Пепперони🍕", callback_data="pizza_Пепперони")
    btn3 = types.InlineKeyboardButton("🍕Гавайская🍕", callback_data="pizza_Гавайская")
    keyboard.add(btn1, btn2, btn3)
    return keyboard

def get_size_keyboard(pizza):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    btn_s = types.InlineKeyboardButton("Маленькая 25см", callback_data=f"{pizza}_size_s")
    btn_m = types.InlineKeyboardButton("Средняя 30см", callback_data=f"{pizza}_size_m")
    btn_l = types.InlineKeyboardButton("Большая 35см", callback_data=f"{pizza}_size_l")
    btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_pizza")
    keyboard.add(btn_s, btn_m, btn_l)
    keyboard.add(btn_back)
    return keyboard

def get_back_to_size_keyboard(pizza):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_back = types.InlineKeyboardButton("🔙 Назад к выбору размера", callback_data="back_to_size")
    keyboard.add(btn_back)
    return keyboard

def get_back_to_quantity_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_back = types.InlineKeyboardButton("🔙 Назад к количеству", callback_data="back_to_quantity")
    keyboard.add(btn_back)
    return keyboard

def get_back_to_address_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_back = types.InlineKeyboardButton("🔙 Назад к адресу", callback_data="back_to_address")
    keyboard.add(btn_back)
    return keyboard

def get_back_to_phone_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_back = types.InlineKeyboardButton("🔙 Назад к телефону", callback_data="back_to_phone")
    keyboard.add(btn_back)
    return keyboard

def get_confirmation_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_order")
    btn_cancel = types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_order")
    keyboard.add(btn_confirm, btn_cancel)
    return keyboard

# ---------- Обработчик команды ----------
@bot.message_handler(commands=['start', 'hello', 'привет'])
def main(message):
    bot.send_message(
        message.chat.id,
        f'Привет - привет, {message.from_user.first_name}!\nВыберите пиццу:',
        reply_markup=get_pizza_keyboard()
    )

# ---------- Обработчик нажатий ----------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    data = call.data
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    # Назад к пицце
    if data == "back_to_pizza":
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text='Выберите пиццу:',
            reply_markup=get_pizza_keyboard()
        )
        return

    # Выбор пиццы
    elif data.startswith("pizza_"):
        pizza = data.replace("pizza_", "")
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f'Вы выбрали {pizza}.\nТеперь выберите размер:',
            reply_markup=get_size_keyboard(pizza)
        )
        return

    # Выбор размера
    elif "_size_" in data:
        pizza, size = data.split("_size_")
        user_data[chat_id] = {'pizza': pizza, 'size': size}
        user_state[chat_id] = 'waiting_quantity'
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"Вы выбрали {pizza} размер {size_names.get(size, size)}.\n"
                 "Теперь введите количество (целое число > 0):",
            reply_markup=get_back_to_size_keyboard(pizza)
        )
        return

    # Назад к размеру
    elif data == "back_to_size":
        pizza = user_data.get(chat_id, {}).get('pizza', '')
        if pizza:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=f'Вы выбрали {pizza}.\nТеперь выберите размер:',
                reply_markup=get_size_keyboard(pizza)
            )
            user_state[chat_id] = None
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text='Выберите пиццу:',
                reply_markup=get_pizza_keyboard()
            )
        return

    # Назад к количеству
    elif data == "back_to_quantity":
        pizza = user_data.get(chat_id, {}).get('pizza', '')
        size = user_data.get(chat_id, {}).get('size', '')
        if pizza and size:
            current_qty = user_data.get(chat_id, {}).get('quantity', 'не указано')
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=f"Вы выбрали {pizza} размер {size_names.get(size, size)}.\n"
                     f"Текущее количество: {current_qty}\n"
                     "Введите новое количество (целое число > 0):",
                reply_markup=get_back_to_size_keyboard(pizza)
            )
            user_state[chat_id] = 'waiting_quantity'
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text='Выберите пиццу:',
                reply_markup=get_pizza_keyboard()
            )
        return

    # Назад к адресу
    elif data == "back_to_address":
        pizza = user_data.get(chat_id, {}).get('pizza', '')
        size = user_data.get(chat_id, {}).get('size', '')
        quantity = user_data.get(chat_id, {}).get('quantity', '')
        if pizza and size and quantity:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=f"Вы выбрали {pizza} размер {size_names.get(size, size)}, количество {quantity}.\n"
                     "Введите адрес доставки:",
                reply_markup=get_back_to_quantity_keyboard()
            )
            user_state[chat_id] = 'waiting_address'
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text='Выберите пиццу:',
                reply_markup=get_pizza_keyboard()
            )
        return

    # Назад к телефону (с этапа подтверждения)
    elif data == "back_to_phone":
        pizza = user_data.get(chat_id, {}).get('pizza', '')
        size = user_data.get(chat_id, {}).get('size', '')
        quantity = user_data.get(chat_id, {}).get('quantity', '')
        address = user_data.get(chat_id, {}).get('address', '')
        if pizza and size and quantity and address:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=f"Вы выбрали {pizza} размер {size_names.get(size, size)}, количество {quantity}, адрес {address}.\n"
                     "Введите номер телефона:",
                reply_markup=get_back_to_address_keyboard()
            )
            user_state[chat_id] = 'waiting_phone'
        else:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text='Выберите пиццу:',
                reply_markup=get_pizza_keyboard()
            )
        return

    # Подтверждение заказа
    elif data == "confirm_order":
        pizza = user_data.get(chat_id, {}).get('pizza', '')
        size = user_data.get(chat_id, {}).get('size', '')
        quantity = user_data.get(chat_id, {}).get('quantity', '')
        address = user_data.get(chat_id, {}).get('address', '')
        phone = user_data.get(chat_id, {}).get('phone', '')

        if pizza and size and quantity and address and phone:
            safe_pizza = html.escape(pizza)
            safe_size = html.escape(size_names.get(size, size))
            safe_quantity = html.escape(str(quantity))
            safe_address = html.escape(address)
            safe_phone = html.escape(phone)
            safe_name = html.escape(call.from_user.first_name or '')
            safe_username = html.escape(call.from_user.username or 'нет')

            admin_text = (
                f"<b>🆕 Новый заказ!</b>\n\n"
                f"🍕 Пицца: {pizza}\n"
                f"📏 Размер: {size_names.get(size, size)}\n"
                f"🔢 Количество: {quantity}\n"
                f"📍 Адрес: {address}\n"
                f"📞 Телефон: {phone}\n"
                f"🆔 Пользователь: {call.from_user.first_name} (@{call.from_user.username or 'нет'})"
            )

            try:
                bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode='HTML')
                admin_ok = True
            except Exception as e:
                print(f"Ошибка: {e}")
                admin_ok = False

            # Сообщение пользователю
            user_text = "✅ Спасибо! Ваш заказ принят и отправлен администратору." if admin_ok else \
                "✅ Спасибо! Ваш заказ принят, но возникла проблема с уведомлением администратора. Мы скоро свяжемся с вами."

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=user_text,
                reply_markup=None
            )

            # Завершаем диалог: удаляем данные и сбрасываем состояние
            if chat_id in user_data:
                del user_data[chat_id]
            user_state[chat_id] = None

        else:
            # Если данных не хватает (защита от ошибок)
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text="❌ Ошибка: не хватает данных для оформления заказа. Начните заказ сначала /start",
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
            text="❌ Заказ отменён.\nВы можете начать заново командой /start",
            reply_markup=None
        )
        if chat_id in user_data:
            del user_data[chat_id]
        user_state[chat_id] = None
        return

# ---------- Обработчик текстовых сообщений ----------
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id

    if user_state.get(chat_id) == 'waiting_quantity':
        try:
            quantity = int(message.text.strip())
            if quantity > 0:
                user_data[chat_id]['quantity'] = quantity
                user_state[chat_id] = 'waiting_address'
                bot.send_message(
                    chat_id,
                    f"Количество: {quantity}.\nТеперь введите адрес доставки:",
                    reply_markup=get_back_to_quantity_keyboard()
                )
            else:
                bot.send_message(chat_id, "❌ Количество должно быть больше 0. Попробуйте ещё раз:")
        except ValueError:
            bot.send_message(chat_id, "❌ Это не число. Введите целое положительное число:")

    elif user_state.get(chat_id) == 'waiting_address':
        address = message.text.strip()
        if len(address) > 5:
            user_data[chat_id]['address'] = address
            user_state[chat_id] = 'waiting_phone'
            bot.send_message(
                chat_id,
                f"Адрес: {address}.\nТеперь введите номер телефона:",
                reply_markup=get_back_to_address_keyboard()
            )
        else:
            bot.send_message(chat_id, "❌ Адрес слишком короткий. Введите полный адрес (минимум 6 символов):")

    elif user_state.get(chat_id) == 'waiting_phone':
        phone = message.text.strip()
        if re.match(r'^\+?\d{10,15}$', phone):
            user_data[chat_id]['phone'] = phone
            user_state[chat_id] = None
            pizza = user_data[chat_id]['pizza']
            size = user_data[chat_id]['size']
            quantity = user_data[chat_id]['quantity']
            address = user_data[chat_id]['address']
            bot.send_message(
                chat_id,
                f"📋 Проверьте ваш заказ:\n\n"
                f"Пицца: {pizza}\n"
                f"Размер: {size_names.get(size, size)}\n"
                f"Количество: {quantity}\n"
                f"Адрес: {address}\n"
                f"Телефон: {phone}\n\n"
                f"Всё верно? Подтвердите или отмените заказ.",
                reply_markup=get_confirmation_keyboard()
            )
        else:
            bot.send_message(chat_id, "❌ Неверный формат телефона. Введите номер (только цифры, возможно с + в начале, от 10 до 15 символов):")

    else:
        bot.send_message(chat_id, "Пожалуйста, используйте кнопки для выбора.")

# ---------- Запуск ----------
import time

if __name__ == '__main__':
    while True:
        try:
            print("Бот запущен. Ожидание обновлений...")
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Бот упал с ошибкой: {e}")
            print("Перезапуск через 5 секунд...")
            time.sleep(5)