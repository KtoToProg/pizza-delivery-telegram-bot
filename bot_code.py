import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import sys
import json
import os
import re

# ---------- НАСТРОЙКА ПРОКСИ ----------
telebot.apihelper.proxy = {
    'http': 'socks5://127.0.0.1:9150',
    'https': 'socks5://127.0.0.1:9150'
}

# ---------- КОНФИГУРАЦИЯ ----------
TOKEN = '8888407391:AAGN1pnRqVzfhsXO7de-rKIznaQBXGwRHPk'  # СМЕНИ ТОКЕН!
SPREADSHEET_ID = '1RwNMtGgNPwt2R7Ns92cWyHV-LXq9Xuz9jd7SZvGujSk'
SHEET_NAME = 'Лист1'
BACKUP_FILE = 'advertisements_backup.json'

# ---------- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ----------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('arena_creds.json', scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# ---------- ЛИСТ ДЛЯ ЛОГОВ ----------
log_sheet = None
try:
    log_sheet = client.open_by_key(SPREADSHEET_ID).worksheet('Логи')
except gspread.exceptions.WorksheetNotFound:
    log_sheet = client.open_by_key(SPREADSHEET_ID).add_worksheet(title='Логи', rows=1000, cols=5)
    log_sheet.append_row(['Дата', 'user_id', 'username', 'Команда', 'Параметры'])

bot = telebot.TeleBot(TOKEN)

# ---------- РЕЗЕРВНОЕ КОПИРОВАНИЕ ----------
def save_ad_to_backup(ad_data):
    ads = []
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                ads = json.load(f)
        except (json.JSONDecodeError, IOError):
            ads = []
    ads.append(ad_data)
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(ads, f, ensure_ascii=False, indent=2)
    print(f"📦 Объявление '{ad_data['Название']}' сохранено в резервный файл")

def retry_failed_ads():
    if not os.path.exists(BACKUP_FILE):
        return
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            ads = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    if not ads:
        return
    print(f"📦 Найдено {len(ads)} неотправленных объявлений. Пытаемся отправить...")
    remaining = []
    for idx, ad in enumerate(ads, 1):
        print(f"⏳ Обработка объявления #{idx}...")
        success = write_ad_to_sheet(ad, max_retries=2, delay=3)
        if success:
            print(f"✅ Резервное объявление #{idx} отправлено")
        else:
            print(f"❌ Резервное объявление #{idx} не удалось отправить, оставляем в резерве")
            remaining.append(ad)
    if remaining:
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining, f, ensure_ascii=False, indent=2)
        print(f"⚠️ {len(remaining)} объявлений остались в резервном файле")
    else:
        if os.path.exists(BACKUP_FILE):
            os.remove(BACKUP_FILE)
            print("🗑️ Резервный файл очищен (все объявления отправлены)")

def write_ad_to_sheet(ad_data, max_retries=3, delay=5):
    all_records = sheet.get_all_records()
    max_id = 0
    for row in all_records:
        try:
            row_id = int(row.get('ID', 0))
            if row_id > max_id:
                max_id = row_id
        except:
            pass
    new_id = max_id + 1

    row = [
        new_id,
        ad_data.get('Аренда или продажа', ''),
        ad_data.get('Тип техники', ''),
        ad_data.get('Название', ''),
        ad_data.get('Марка', ''),
        ad_data.get('Год выпуска', ''),
        ad_data.get('Состояние', ''),
        ad_data.get('Технические характеристики', ''),
        ad_data.get('Наличие документов', ''),
        ad_data.get('Регион', ''),
        ad_data.get('Условия доставки', ''),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        ad_data.get('Цена', ''),
        ad_data.get('Фото_URL', '')
    ]

    for attempt in range(1, max_retries + 1):
        try:
            sheet.append_row(row)
            print(f"✅ Объявление '{ad_data['Название']}' записано в таблицу (попытка {attempt})")
            return True
        except Exception as e:
            print(f"⚠️ Попытка {attempt} записи не удалась: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    return False

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_all_listings():
    return sheet.get_all_records()

def get_listings_by_category(category_type, subcategory=None):
    all_listings = get_all_listings()
    filtered = []
    for item in all_listings:
        item_cat = str(item.get('Аренда или продажа', '')).strip().lower()
        item_type = str(item.get('Тип техники', '')).strip().lower()
        if category_type.lower() not in item_cat:
            continue
        if subcategory:
            if subcategory.lower() not in item_type:
                continue
        filtered.append(item)
    return filtered

def get_listing_by_id(listing_id):
    all_listings = get_all_listings()
    for item in all_listings:
        if str(item.get('ID', '')).strip() == str(listing_id).strip():
            return item
    return None

def get_latest_listings(limit=10):
    all_listings = get_all_listings()
    try:
        sorted_list = sorted(all_listings, key=lambda x: x.get('Время', ''), reverse=True)
    except:
        sorted_list = all_listings[::-1]
    return sorted_list[:limit]

def format_listing_text(listing):
    text = f"🚜 *{listing.get('Название', 'Без названия')}*\n"
    text += f"Марка: {listing.get('Марка', '—')}\n"
    text += f"Год выпуска: {listing.get('Год выпуска', '—')}\n"
    text += f"Состояние: {listing.get('Состояние', '—')}\n"
    text += f"Тип техники: {listing.get('Тип техники', '—')}\n"
    text += f"Аренда или продажа: {listing.get('Аренда или продажа', '—')}\n"
    if listing.get('Технические характеристики'):
        text += f"Характеристики: {listing.get('Технические характеристики')}\n"
    if listing.get('Наличие документов'):
        text += f"Документы: {listing.get('Наличие документов')}\n"
    if listing.get('Регион'):
        text += f"Регион: {listing.get('Регион')}\n"
    if listing.get('Условия доставки'):
        text += f"Условия доставки: {listing.get('Условия доставки')}\n"
    if listing.get('Цена'):
        text += f"Цена: {listing.get('Цена')} руб.\n"
    return text

def log_to_sheet(command, params, user_id, username):
    if log_sheet:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_sheet.append_row([now, str(user_id), username or '', command, params])

# ---------- ФИЛЬТРЫ И ПАГИНАЦИЯ ----------
def apply_filters(listings, filters):
    result = listings
    if 'price_min' in filters and 'price_max' in filters:
        try:
            p_min = float(filters['price_min'])
            p_max = float(filters['price_max'])
            result = [item for item in result if
                      item.get('Цена') and p_min <= float(item.get('Цена', 0)) <= p_max]
        except:
            pass
    if 'year' in filters:
        year_str = filters['year'].strip()
        if year_str.isdigit():
            year = int(year_str)
            result = [item for item in result if str(item.get('Год выпуска', '')).isdigit() and int(item.get('Год выпуска', 0)) == year]
    if 'region' in filters:
        region = filters['region'].strip().lower()
        result = [item for item in result if region in str(item.get('Регион', '')).lower()]
    return result

def send_listings_list(chat_id, listings, title="Объявления", page=0, per_page=5, callback_prefix='list'):
    if not listings:
        bot.send_message(chat_id, "Нет объявлений.")
        return
    total = len(listings)
    total_pages = (total + per_page - 1) // per_page
    if page >= total_pages:
        page = total_pages - 1
    if page < 0:
        page = 0
    start = page * per_page
    end = min(start + per_page, total)
    page_listings = listings[start:end]

    user_pages[chat_id] = {
        'listings': listings,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'callback_prefix': callback_prefix,
        'title': title
    }

    text = f"*{title}* (стр. {page + 1}/{total_pages})\n\n"
    for idx, item in enumerate(page_listings, start=start + 1):
        listing_id = item.get('ID', idx)
        text += f"{idx}. {item.get('Название', 'Без названия')} — {item.get('Марка', '')}\n"

    markup = types.InlineKeyboardMarkup(row_width=3)
    for idx, item in enumerate(page_listings, start=start + 1):
        listing_id = item.get('ID', idx)
        markup.add(types.InlineKeyboardButton(f"{idx}", callback_data=f"{callback_prefix}_view_{listing_id}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"{callback_prefix}_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton("Вперёд ➡️", callback_data=f"{callback_prefix}_page_{page + 1}"))
    if nav_buttons:
        markup.add(*nav_buttons)

    markup.add(types.InlineKeyboardButton("🏠 В главное меню", callback_data='main_menu'))
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

# ---------- ХРАНИЛИЩА ----------
user_pages = {}
user_filters = {}
user_ad_data = {}
ad_states = {}

def get_ad_state(chat_id):
    return ad_states.get(chat_id, [None])[-1] if chat_id in ad_states and ad_states[chat_id] else None

def push_ad_state(chat_id, state):
    if chat_id not in ad_states:
        ad_states[chat_id] = []
    ad_states[chat_id].append(state)

def pop_ad_state(chat_id):
    if chat_id in ad_states and len(ad_states[chat_id]) > 1:
        ad_states[chat_id].pop()
        return ad_states[chat_id][-1]
    return None

def clear_ad_state(chat_id):
    if chat_id in ad_states:
        del ad_states[chat_id]

def remove_keyboard(chat_id):
    if chat_id in user_ad_data and 'last_bot_msg_id' in user_ad_data[chat_id]:
        try:
            bot.edit_message_reply_markup(chat_id, user_ad_data[chat_id]['last_bot_msg_id'], reply_markup=None)
        except:
            pass

# ---------- КОМАНДА /new ----------
@bot.message_handler(commands=['new'])
def start_new_ad(message):
    chat_id = message.chat.id
    user_ad_data[chat_id] = {}
    push_ad_state(chat_id, 'ad_type')
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🚜 Аренда", callback_data='ad_type_аренда'),
        types.InlineKeyboardButton("💰 Продажа", callback_data='ad_type_продажа')
    )
    markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
    msg = bot.send_message(chat_id, "Начнём создание объявления.\nВыберите тип:", reply_markup=markup)
    user_ad_data[chat_id]['last_bot_msg_id'] = msg.message_id

# ---------- ОБРАБОТЧИК CALLBACK ----------
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if data.startswith('ad_type_'):
        ad_type = data.replace('ad_type_', '')
        user_ad_data[chat_id]['Аренда или продажа'] = ad_type
        push_ad_state(chat_id, 'ad_sub')
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Наземная техника", callback_data='ad_sub_наземная'),
            types.InlineKeyboardButton("Водная техника", callback_data='ad_sub_водная'),
            types.InlineKeyboardButton("Воздушная/подводная/космическая", callback_data='ad_sub_воздушная')
        )
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        bot.edit_message_text("Выберите тип техники:", chat_id, message_id, reply_markup=markup)
        user_ad_data[chat_id]['last_bot_msg_id'] = message_id

    elif data.startswith('ad_sub_'):
        sub_map = {
            'наземная': 'Наземная техника',
            'водная': 'Водная техника',
            'воздушная': 'Воздушная, подводная, космическая'
        }
        sub_key = data.replace('ad_sub_', '')
        sub = sub_map.get(sub_key, sub_key)
        user_ad_data[chat_id]['Тип техники'] = sub
        push_ad_state(chat_id, 'ad_title')
        bot.edit_message_text("Введите название техники (например: Экскаватор):", chat_id, message_id)
        user_ad_data[chat_id]['last_bot_msg_id'] = message_id
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите название:", reply_markup=markup)
        user_ad_data[chat_id]['last_bot_msg_id'] = msg.message_id

    elif data == 'ad_back':
        prev_state = pop_ad_state(chat_id)
        if prev_state is None:
            clear_ad_state(chat_id)
            if chat_id in user_ad_data:
                del user_ad_data[chat_id]
            bot.edit_message_text("Создание объявления отменено.", chat_id, message_id)
            return
        try:
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
        except:
            pass
        show_step(chat_id)

    elif data == 'ad_cancel':
        if chat_id in user_ad_data:
            del user_ad_data[chat_id]
        clear_ad_state(chat_id)
        bot.edit_message_text("Создание объявления отменено.", chat_id, message_id)
        bot.send_message(chat_id, "Вы можете начать заново командой /new")

    # ----- ОБРАБОТКА ВЫБОРА СОСТОЯНИЯ -----
    elif data.startswith('ad_cond_'):
        condition = data.replace('ad_cond_', '')
        user_ad_data[chat_id]['Состояние'] = condition
        push_ad_state(chat_id, 'ad_specs')
        show_step(chat_id)

    # ----- ОБРАБОТКА ВЫБОРА ДОКУМЕНТОВ -----
    elif data.startswith('ad_docs_'):
        docs = data.replace('ad_docs_', '')
        user_ad_data[chat_id]['Наличие документов'] = docs
        push_ad_state(chat_id, 'ad_region')
        show_step(chat_id)

    elif data == 'ad_confirm':
        required_fields = ['Аренда или продажа', 'Тип техники', 'Название', 'Марка', 'Год выпуска',
                           'Состояние', 'Технические характеристики', 'Наличие документов',
                           'Регион', 'Условия доставки', 'Цена']
        ad = user_ad_data.get(chat_id, {})
        missing = [f for f in required_fields if not ad.get(f, '').strip()]
        if missing:
            bot.answer_callback_query(call.id, f"Заполните все поля: {', '.join(missing)}", show_alert=True)
            return
        success = write_ad_to_sheet(ad, max_retries=3, delay=5)
        if success:
            bot.edit_message_text("✅ Ваше объявление успешно добавлено!", chat_id, message_id)
            log_to_sheet('/new', f"Добавлено объявление: {ad['Название']}", call.from_user.id, call.from_user.username)
        else:
            save_ad_to_backup(ad)
            bot.edit_message_text(
                "⚠️ Ваше объявление сохранено, но произошла техническая задержка. "
                "Оно будет добавлено автоматически в ближайшее время.",
                chat_id, message_id
            )
            log_to_sheet('/new', f"Объявление сохранено в резерв: {ad['Название']}", call.from_user.id, call.from_user.username)
        if chat_id in user_ad_data:
            del user_ad_data[chat_id]
        clear_ad_state(chat_id)

    # ----- СТАРЫЕ ОБРАБОТЧИКИ -----
    elif data == 'cat_rent':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Наземная техника", callback_data='sub_rent_Наземная'),
            types.InlineKeyboardButton("Водная техника", callback_data='sub_rent_Водная'),
            types.InlineKeyboardButton("Воздушная/подводная/космическая", callback_data='sub_rent_Воздушная')
        )
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='categories_back'))
        bot.edit_message_text("Выберите подкатегорию (Аренда):", chat_id, message_id, reply_markup=markup)

    elif data == 'cat_sale':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Наземная техника", callback_data='sub_sale_Наземная'),
            types.InlineKeyboardButton("Водная техника", callback_data='sub_sale_Водная'),
            types.InlineKeyboardButton("Воздушная/подводная/космическая", callback_data='sub_sale_Воздушная')
        )
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='categories_back'))
        bot.edit_message_text("Выберите подкатегорию (Продажа):", chat_id, message_id, reply_markup=markup)

    elif data == 'categories_back':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🚜 Аренда", callback_data='cat_rent'),
            types.InlineKeyboardButton("💰 Продажа", callback_data='cat_sale')
        )
        bot.edit_message_text("Выберите тип объявлений:", chat_id, message_id, reply_markup=markup)

    elif data.startswith('sub_rent_') or data.startswith('sub_sale_'):
        parts = data.split('_', 2)
        if len(parts) < 3:
            return
        type_part = parts[1]
        sub = parts[2]
        category_type = 'аренда' if type_part == 'rent' else 'продажа'
        listings = get_listings_by_category(category_type, sub)
        if not listings:
            bot.answer_callback_query(call.id, "В этой категории пока нет объявлений.", show_alert=True)
            return
        prefix = f"{type_part}_{sub}"
        send_listings_list(chat_id, listings, title=f"{category_type.capitalize()} — {sub}", page=0, per_page=5, callback_prefix=prefix)
        log_to_sheet('/categories', f"{category_type} {sub}", call.from_user.id, call.from_user.username)

    elif '_page_' in data:
        parts = data.rsplit('_', 1)
        if len(parts) != 2 or not parts[1].isdigit():
            return
        page = int(parts[1])
        user_data = user_pages.get(chat_id)
        if not user_data:
            bot.answer_callback_query(call.id, "Данные устарели, попробуйте заново.", show_alert=True)
            return
        listings = user_data['listings']
        per_page = user_data['per_page']
        total_pages = user_data['total_pages']
        prefix = user_data['callback_prefix']
        title = user_data.get('title', 'Объявления')
        if page >= total_pages:
            page = total_pages - 1
        bot.delete_message(chat_id, message_id)
        send_listings_list(chat_id, listings, title=title, page=page, per_page=per_page, callback_prefix=prefix)

    elif '_view_' in data:
        parts = data.rsplit('_', 1)
        if len(parts) != 2:
            return
        listing_id = parts[1]
        listing = get_listing_by_id(listing_id)
        if not listing:
            bot.answer_callback_query(call.id, "Объявление не найдено.", show_alert=True)
            return
        text = format_listing_text(listing)
        markup = types.InlineKeyboardMarkup()
        site_url = listing.get('Ссылка_на_сайт', '')
        if not site_url:
            site_url = f"https://аренаспецтех.рф/объявление/{listing.get('ID', '')}"
        btn_site = types.InlineKeyboardButton("🌐 Смотреть на сайте", url=site_url)
        markup.add(btn_site)
        btn_back = types.InlineKeyboardButton("🔙 Назад к списку", callback_data='back_to_list')
        markup.add(btn_back)
        photo_url = listing.get('Фото_URL', '').strip()
        if photo_url:
            try:
                bot.send_photo(chat_id, photo_url, caption=text, reply_markup=markup, parse_mode='Markdown')
            except:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
        bot.delete_message(chat_id, message_id)
        log_to_sheet('/view', f"ID {listing_id}", call.from_user.id, call.from_user.username)

    elif data == 'back_to_list':
        user_data = user_pages.get(chat_id)
        if not user_data:
            bot.send_message(chat_id, "Список устарел, воспользуйтесь /categories")
            return
        listings = user_data['listings']
        page = user_data['page']
        per_page = user_data['per_page']
        prefix = user_data['callback_prefix']
        title = user_data.get('title', 'Объявления')
        bot.delete_message(chat_id, message_id)
        send_listings_list(chat_id, listings, title=title, page=page, per_page=per_page, callback_prefix=prefix)

    elif data == 'main_menu':
        bot.delete_message(chat_id, message_id)
        fake_message = types.Message(
            message_id=message_id,
            from_user=call.from_user,
            date=int(time.time()),
            chat=call.message.chat,
            content_type='text',
            options={}
        )
        send_welcome(fake_message)

    # ----- ФИЛЬТР -----
    elif data.startswith('filter_'):
        if data == 'filter_price':
            bot.edit_message_text("Введите минимальную и максимальную цену через пробел (например: 1000 5000):", chat_id, message_id)
            user_filters[chat_id]['step'] = 'waiting_price'
            bot.answer_callback_query(call.id)
        elif data == 'filter_year':
            bot.edit_message_text("Введите год выпуска (например: 2020):", chat_id, message_id)
            user_filters[chat_id]['step'] = 'waiting_year'
            bot.answer_callback_query(call.id)
        elif data == 'filter_region':
            bot.edit_message_text("Введите регион (например: Москва):", chat_id, message_id)
            user_filters[chat_id]['step'] = 'waiting_region'
            bot.answer_callback_query(call.id)
        elif data == 'filter_apply':
            state = user_filters.get(chat_id)
            if not state:
                bot.answer_callback_query(call.id, "Нет активного фильтра.", show_alert=True)
                return
            filtered = apply_filters(state['listings'], state['filters'])
            if not filtered:
                bot.edit_message_text("По вашим фильтрам ничего не найдено.", chat_id, message_id)
            else:
                bot.delete_message(chat_id, message_id)
                send_listings_list(chat_id, filtered, title="🔎 Отфильтрованные объявления", page=0, per_page=5, callback_prefix='filter_result')
                log_to_sheet('/filter', str(state['filters']), call.from_user.id, call.from_user.username)
            del user_filters[chat_id]
            bot.answer_callback_query(call.id)
        elif data == 'filter_reset':
            if chat_id in user_filters:
                user_filters[chat_id]['filters'] = {}
                bot.edit_message_text("Все фильтры сброшены. Вы можете добавить новые.", chat_id, message_id)
            else:
                bot.answer_callback_query(call.id, "Нет активного фильтра.", show_alert=True)
        elif data == 'filter_cancel':
            if chat_id in user_filters:
                del user_filters[chat_id]
            bot.delete_message(chat_id, message_id)
            bot.send_message(chat_id, "Фильтр отменён.")
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "Неизвестная команда")

    else:
        bot.answer_callback_query(call.id, "Неизвестная команда")

# ---------- ПОКАЗ ШАГА ----------
def show_step(chat_id):
    state = get_ad_state(chat_id)
    if state is None:
        bot.send_message(chat_id, "Ошибка. Начните заново /new")
        return

    remove_keyboard(chat_id)

    data = user_ad_data.get(chat_id, {})
    if state == 'ad_type':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🚜 Аренда", callback_data='ad_type_аренда'),
            types.InlineKeyboardButton("💰 Продажа", callback_data='ad_type_продажа')
        )
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Выберите тип:", reply_markup=markup)

    elif state == 'ad_sub':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Наземная техника", callback_data='ad_sub_наземная'),
            types.InlineKeyboardButton("Водная техника", callback_data='ad_sub_водная'),
            types.InlineKeyboardButton("Воздушная/подводная/космическая", callback_data='ad_sub_воздушная')
        )
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Выберите тип техники:", reply_markup=markup)

    elif state == 'ad_title':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите название техники (например: Экскаватор):", reply_markup=markup)

    elif state == 'ad_brand':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите марку техники (например: CAT):", reply_markup=markup)

    elif state == 'ad_year':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите год выпуска (число от 1900 до текущего):", reply_markup=markup)

    elif state == 'ad_condition':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🆕 Новое", callback_data='ad_cond_Новое'),
            types.InlineKeyboardButton("🔄 Б/У", callback_data='ad_cond_Б/У'),
            types.InlineKeyboardButton("💪 Толкнуть, поедет", callback_data='ad_cond_Толкнуть, поедет')
        )
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Выберите состояние техники:", reply_markup=markup)

    elif state == 'ad_specs':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите технические характеристики (минимум 5 символов):", reply_markup=markup)

    elif state == 'ad_docs':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Есть", callback_data='ad_docs_Есть'),
            types.InlineKeyboardButton("❌ Отсутствуют", callback_data='ad_docs_Отсутствуют')
        )
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Наличие документов:", reply_markup=markup)

    elif state == 'ad_region':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите регион (только буквы, минимум 3 символа):", reply_markup=markup)

    elif state == 'ad_delivery':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите условия доставки (только буквы, минимум 3 символа):", reply_markup=markup)

    elif state == 'ad_price':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Введите цену в рублях (только число):", reply_markup=markup)

    elif state == 'ad_photo':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'))
        markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel'))
        msg = bot.send_message(chat_id, "Загрузите фото (прикрепите файл) или введите ссылку (или /skip):", reply_markup=markup)

    elif state == 'ad_confirm':
        ad = user_ad_data.get(chat_id, {})
        preview = (
            "📋 Проверьте данные объявления:\n\n"
            f"Тип: {ad.get('Аренда или продажа', '—')}\n"
            f"Тип техники: {ad.get('Тип техники', '—')}\n"
            f"Название: {ad.get('Название', '—')}\n"
            f"Марка: {ad.get('Марка', '—')}\n"
            f"Год выпуска: {ad.get('Год выпуска', '—')}\n"
            f"Состояние: {ad.get('Состояние', '—')}\n"
            f"Характеристики: {ad.get('Технические характеристики', '—')}\n"
            f"Документы: {ad.get('Наличие документов', '—')}\n"
            f"Регион: {ad.get('Регион', '—')}\n"
            f"Доставка: {ad.get('Условия доставки', '—')}\n"
            f"Цена: {ad.get('Цена', '—')} руб.\n"
            f"Фото: {ad.get('Фото_URL', 'не указано')}\n"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data='ad_confirm'),
            types.InlineKeyboardButton("🔙 Назад", callback_data='ad_back'),
            types.InlineKeyboardButton("❌ Отменить", callback_data='ad_cancel')
        )
        msg = bot.send_message(chat_id, preview, reply_markup=markup)

    else:
        msg = bot.send_message(chat_id, "Ошибка: неизвестный шаг. Начните заново /new")
        clear_ad_state(chat_id)
        if chat_id in user_ad_data:
            del user_ad_data[chat_id]
        return

    user_ad_data[chat_id]['last_bot_msg_id'] = msg.message_id

# ---------- ОБРАБОТЧИК ВВОДА ----------
@bot.message_handler(func=lambda message: get_ad_state(message.chat.id) is not None, content_types=['text', 'photo'])
def handle_ad_input(message):
    chat_id = message.chat.id
    state = get_ad_state(chat_id)

    if message.content_type == 'photo':
        if state == 'ad_photo':
            file_id = message.photo[-1].file_id
            user_ad_data[chat_id]['Фото_URL'] = f"photo_file_id:{file_id}"
            push_ad_state(chat_id, 'ad_confirm')
            show_step(chat_id)
        else:
            bot.reply_to(message, "Пожалуйста, следуйте инструкциям. Сейчас ожидается ввод текста или выбор кнопок.")
        return

    if message.content_type != 'text':
        return

    text = message.text.strip()
    if not text:
        bot.reply_to(message, "Пожалуйста, введите непустое значение.")
        return

    if text.lower() == '/skip' and state == 'ad_photo':
        user_ad_data[chat_id]['Фото_URL'] = ''
        push_ad_state(chat_id, 'ad_confirm')
        show_step(chat_id)
        return

    if state == 'ad_title':
        if len(text) < 2:
            bot.reply_to(message, "❌ Название должно содержать минимум 2 символа.")
            return
        user_ad_data[chat_id]['Название'] = text
        push_ad_state(chat_id, 'ad_brand')
        show_step(chat_id)

    elif state == 'ad_brand':
        if len(text) < 2:
            bot.reply_to(message, "❌ Марка должна содержать минимум 2 символа.")
            return
        user_ad_data[chat_id]['Марка'] = text
        push_ad_state(chat_id, 'ad_year')
        show_step(chat_id)

    elif state == 'ad_year':
        if not text.isdigit() or not (1900 <= int(text) <= datetime.now().year):
            bot.reply_to(message, f"❌ Введите год числом от 1900 до {datetime.now().year}.")
            return
        user_ad_data[chat_id]['Год выпуска'] = text
        push_ad_state(chat_id, 'ad_condition')
        show_step(chat_id)

    elif state == 'ad_condition':
        bot.reply_to(message, "Используйте кнопки для выбора состояния.")
        return

    elif state == 'ad_specs':
        if len(text) < 5:
            bot.reply_to(message, "❌ Характеристики должны содержать минимум 5 символов.")
            return
        if not re.match(r'^[а-яА-ЯёЁa-zA-Z0-9 ,.\-]+$', text):
            bot.reply_to(message, "❌ Разрешены только буквы, цифры, пробелы, запятые, точки и дефисы.")
            return
        user_ad_data[chat_id]['Технические характеристики'] = text
        push_ad_state(chat_id, 'ad_docs')
        show_step(chat_id)

    elif state == 'ad_docs':
        bot.reply_to(message, "Используйте кнопки для выбора наличия документов.")
        return

    elif state == 'ad_region':
        if len(text) < 3:
            bot.reply_to(message, "❌ Регион должен содержать минимум 3 символа.")
            return
        if not re.match(r'^[а-яА-ЯёЁa-zA-Z \-]+$', text):
            bot.reply_to(message, "❌ Разрешены только буквы, пробелы и дефисы.")
            return
        user_ad_data[chat_id]['Регион'] = text
        push_ad_state(chat_id, 'ad_delivery')
        show_step(chat_id)

    elif state == 'ad_delivery':
        if len(text) < 3:
            bot.reply_to(message, "❌ Условия доставки должны содержать минимум 3 символа.")
            return
        if not re.match(r'^[а-яА-ЯёЁa-zA-Z ,.\-]+$', text):
            bot.reply_to(message, "❌ Разрешены только буквы, пробелы, запятые, точки и дефисы.")
            return
        user_ad_data[chat_id]['Условия доставки'] = text
        push_ad_state(chat_id, 'ad_price')
        show_step(chat_id)

    elif state == 'ad_price':
        try:
            price = float(text.replace(',', '.'))
            if price <= 0:
                raise ValueError
            user_ad_data[chat_id]['Цена'] = str(price)
            push_ad_state(chat_id, 'ad_photo')
            show_step(chat_id)
        except:
            bot.reply_to(message, "❌ Введите корректную цену (положительное число, например: 1500000.50)")

    elif state == 'ad_photo':
        if re.match(r'^https?://\S+$', text):
            user_ad_data[chat_id]['Фото_URL'] = text
            push_ad_state(chat_id, 'ad_confirm')
            show_step(chat_id)
        else:
            bot.reply_to(message, "❌ Это не похоже на ссылку. Введите ссылку, начиная с http:// или https://, либо отправьте фото файлом, либо введите /skip для пропуска.")

    elif state == 'ad_confirm':
        bot.reply_to(message, "Используйте кнопки для подтверждения или отмены.")

    else:
        bot.reply_to(message, "Что-то пошло не так. Начните заново командой /new")

# ---------- ОСТАЛЬНЫЕ КОМАНДЫ ----------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Добро пожаловать в бот «АренаСпецТех.РФ»!\n\n"
        "Я помогу вам найти спецтехнику и транспорт в аренду, лизинг или на продажу.\n\n"
        "На платформе представлены объявления по следующим категориям:\n"
        "• Наземная техника (колёсная, гусеничная, рельсовая, стационарная)\n"
        "• Водная техника (баржи, паромы, рыболовецкие суда, малые суда)\n"
        "• Воздушная, подводная и космическая техника\n\n"
        "На сайте пока нет актуальных объявлений. Только тестовые.\n\n"
        "Есть бесплатное размещение объявлений!\n\n"
        "Доступные команды:\n"
        "/categories — посмотреть категории\n"
        "/latest — свежие объявления\n"
        "/search [запрос] — поиск\n"
        "/filter — интерактивный фильтр по цене, году, региону\n"
        "/new — добавить своё объявление\n"
        "/help — помощь"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    log_to_sheet('/start', '', message.from_user.id, message.from_user.username)

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "Справка по использованию бота:\n\n"
        "/start — главное меню\n"
        "/categories — выбор категорий (аренда/продажа, затем тип техники)\n"
        "/latest — последние 10 объявлений\n"
        "/search [текст] — поиск по названию или марке\n"
        "/filter — интерактивный фильтр: выберите параметр (цена, год, регион), введите значение, затем примените или добавьте ещё фильтры.\n"
        "/new — создать своё объявление (пошаговый мастер)\n\n"
        "В каждом списке объявлений можно нажать на кнопку с номером, чтобы увидеть детали."
    )
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['categories'])
def categories_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚜 Аренда", callback_data='cat_rent'),
        types.InlineKeyboardButton("💰 Продажа", callback_data='cat_sale')
    )
    bot.send_message(message.chat.id, "Выберите тип объявлений:", reply_markup=markup)

@bot.message_handler(commands=['latest'])
def latest_listings(message):
    listings = get_latest_listings(10)
    if not listings:
        bot.reply_to(message, "Объявлений пока нет.")
        return
    send_listings_list(message.chat.id, listings, title="📌 Свежие объявления")
    log_to_sheet('/latest', '', message.from_user.id, message.from_user.username)

@bot.message_handler(commands=['search'])
def search_listings(message):
    query = message.text.replace('/search', '').strip()
    if not query:
        bot.reply_to(message, "Введите запрос после команды, например: /search экскаватор")
        return
    all_listings = get_all_listings()
    found = []
    for item in all_listings:
        name = str(item.get('Название', '')).lower()
        mark = str(item.get('Марка', '')).lower()
        if query.lower() in name or query.lower() in mark:
            found.append(item)
    if not found:
        bot.reply_to(message, f"По запросу «{query}» ничего не найдено.")
        return
    send_listings_list(message.chat.id, found, title=f"🔍 Результаты поиска: {query}")
    log_to_sheet('/search', query, message.from_user.id, message.from_user.username)

@bot.message_handler(commands=['filter'])
def start_filter(message):
    chat_id = message.chat.id
    user_filters[chat_id] = {
        'filters': {},
        'listings': get_all_listings(),
        'step': 'choose'
    }
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Цена", callback_data='filter_price'),
        types.InlineKeyboardButton("📅 Год", callback_data='filter_year'),
        types.InlineKeyboardButton("📍 Регион", callback_data='filter_region'),
        types.InlineKeyboardButton("✅ Применить", callback_data='filter_apply'),
        types.InlineKeyboardButton("❌ Сбросить", callback_data='filter_reset'),
        types.InlineKeyboardButton("❌ Отмена", callback_data='filter_cancel')
    )
    bot.send_message(chat_id, "Выберите параметр для фильтрации. После добавления всех условий нажмите «Применить».", reply_markup=markup)

@bot.message_handler(func=lambda message: message.chat.id in user_filters and user_filters[message.chat.id].get('step', '').startswith('waiting_'))
def handle_filter_input(message):
    chat_id = message.chat.id
    state = user_filters[chat_id]['step']
    filters = user_filters[chat_id]['filters']
    text = message.text.strip()

    if state == 'waiting_price':
        parts = text.split()
        if len(parts) == 2 and parts[0].replace('.', '', 1).isdigit() and parts[1].replace('.', '', 1).isdigit():
            filters['price_min'] = float(parts[0])
            filters['price_max'] = float(parts[1])
            bot.reply_to(message, f"✅ Цена от {parts[0]} до {parts[1]} установлена.")
        else:
            bot.reply_to(message, "❌ Некорректный ввод. Введите два числа через пробел (например: 1000 5000).")
            return
    elif state == 'waiting_year':
        if text.isdigit():
            filters['year'] = text
            bot.reply_to(message, f"✅ Год выпуска установлен: {text}")
        else:
            bot.reply_to(message, "❌ Введите год числом (например: 2020).")
            return
    elif state == 'waiting_region':
        filters['region'] = text
        bot.reply_to(message, f"✅ Регион установлен: {text}")

    user_filters[chat_id]['step'] = 'choose'
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Цена", callback_data='filter_price'),
        types.InlineKeyboardButton("📅 Год", callback_data='filter_year'),
        types.InlineKeyboardButton("📍 Регион", callback_data='filter_region'),
        types.InlineKeyboardButton("✅ Применить", callback_data='filter_apply'),
        types.InlineKeyboardButton("❌ Сбросить", callback_data='filter_reset'),
        types.InlineKeyboardButton("❌ Отмена", callback_data='filter_cancel')
    )
    bot.send_message(chat_id, "Текущие фильтры: " + str(filters) + "\nВыберите действие:", reply_markup=markup)

# ---------- ЗАПУСК ----------
if __name__ == '__main__':
    retry_failed_ads()
    print("Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except KeyboardInterrupt:
            print("Бот остановлен пользователем.")
            break
        except Exception as e:
            print(f"Бот упал с ошибкой: {e}")
            print("Перезапуск через 5 секунд...")
            time.sleep(5)
