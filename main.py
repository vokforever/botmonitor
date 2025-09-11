import asyncio
import aiohttp
import logging
import sqlite3
import idna  # для работы с Punycode
import ssl
import socket
import OpenSSL
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.command import Command
from aiogram.types import Message

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота (вставьте свой API_TOKEN)
API_TOKEN = '7253515169:AAHK3c9wIC2vlSVn7yPi5EDkZopW9g_iVKs'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Интервал проверки в секундах
CHECK_INTERVAL = 300  # 5 минут
SSL_WARNING_DAYS = 30  # Предупреждение о сроке истечения SSL сертификата (в днях)


def update_db():
    conn = sqlite3.connect('sites_monitor.db')
    cursor = conn.cursor()
    try:
        cursor.execute('ALTER TABLE sites ADD COLUMN original_url TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        # Column might already exist
        pass
    conn.close()

# Функция для обработки URL с поддержкой IDN (Internationalized Domain Names)
def process_url(url):
    url = url.strip()

    # Добавляем протокол, если его нет
    if not (url.startswith('http://') or url.startswith('https://')):
        url = 'https://' + url

    # Разбираем URL на части
    protocol_end = url.find('://')
    if protocol_end != -1:
        protocol = url[:protocol_end + 3]
        remaining = url[protocol_end + 3:]

        # Ищем первый слеш после протокола
        path_start = remaining.find('/')
        if path_start != -1:
            domain = remaining[:path_start]
            path = remaining[path_start:]
        else:
            domain = remaining
            path = ''

        # Преобразуем кириллический домен в punycode
        try:
            punycode_domain = idna.encode(domain).decode('ascii')
            return protocol + punycode_domain + path
        except Exception as e:
            logging.error(f"Error converting domain to punycode: {e}")
            return url

    return url


# Функция проверки SSL сертификата
async def check_ssl_certificate(url):
    try:
        # Извлекаем домен из URL
        protocol_end = url.find('://')
        if protocol_end != -1:
            remaining = url[protocol_end + 3:]
            path_start = remaining.find('/')
            if path_start != -1:
                domain = remaining[:path_start]
            else:
                domain = remaining

            # Создаем контекст SSL
            context = ssl.create_default_context()

            # Устанавливаем соединение
            with socket.create_connection((domain, 443)) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert(binary_form=True)
                    x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert)

                    # Получаем срок действия сертификата
                    expiry_date = datetime.strptime(x509.get_notAfter().decode('ascii'), '%Y%m%d%H%M%SZ')
                    issuer = dict(x509.get_issuer().get_components())
                    issuer_name = issuer.get(b'CN', b'Unknown').decode('utf-8')
                    subject = dict(x509.get_subject().get_components())
                    subject_name = subject.get(b'CN', b'Unknown').decode('utf-8')

                    days_left = (expiry_date - datetime.now()).days

                    return {
                        'has_ssl': True,
                        'expiry_date': expiry_date,
                        'days_left': days_left,
                        'issuer': issuer_name,
                        'subject': subject_name,
                        'expires_soon': days_left <= SSL_WARNING_DAYS,
                        'expired': days_left <= 0
                    }
    except Exception as e:
        logging.error(f"Error checking SSL certificate: {e}")
        return {
            'has_ssl': False,
            'error': str(e)
        }


# Настройка базы данных
def init_db():
    conn = sqlite3.connect('sites_monitor.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY,
        url TEXT NOT NULL,
        original_url TEXT,
        user_id INTEGER NOT NULL,
        is_up BOOLEAN DEFAULT 1,
        has_ssl BOOLEAN DEFAULT 0,
        ssl_expires_at TIMESTAMP,
        last_check TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()


# Состояния для добавления сайта
class AddSite(StatesGroup):
    waiting_for_url = State()


# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я бот для мониторинга доступности сайтов.\n\n"
        "Команды:\n"
        "/add - добавить сайт для мониторинга\n"
        "/list - показать список отслеживаемых сайтов\n"
        "/remove - удалить сайт из мониторинга\n"
        "/status - проверить статус всех сайтов\n"
        "/help - показать справку"
    )


# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ Справка по командам:\n\n"
        "/add - добавить новый сайт для мониторинга\n"
        "/list - показать список всех отслеживаемых вами сайтов\n"
        "/remove - удалить сайт из мониторинга\n"
        "/status - выполнить проверку статуса всех сайтов\n"
        "/help - показать эту справку\n\n"
        "Бот автоматически проверяет доступность сайтов каждые 5 минут.\n"
        "Вы можете добавлять сайты с кириллическими доменами (например, цифровизируем.рф).\n"
        "Протокол (http:// или https://) добавляется автоматически, если не указан.\n"
        "Для HTTPS сайтов дополнительно проверяется SSL сертификат и срок его действия."
    )


# Обработчик команды /add
@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await state.set_state(AddSite.waiting_for_url)
    await message.answer("Отправьте URL сайта, который хотите мониторить.\nНапример: example.com или цифровизируем.рф")


# Получение URL для добавления
@dp.message(AddSite.waiting_for_url)
async def process_url_input(message: Message, state: FSMContext):
    original_url = message.text.strip()
    url = process_url(original_url)

    conn = sqlite3.connect('sites_monitor.db')
    cursor = conn.cursor()

    # Проверка, существует ли уже такой URL для этого пользователя
    cursor.execute("SELECT id FROM sites WHERE url = ? AND user_id = ?", (url, message.from_user.id))
    existing = cursor.fetchone()

    if existing:
        await message.answer(f"⚠️ Сайт {original_url} уже добавлен в мониторинг.")
        conn.close()
        await state.clear()
        return

    # Сначала сообщаем о начале проверки
    status_msg = await message.answer(f"🔄 Проверяю доступность сайта {original_url}...")

    # Проверяем доступность сайта перед добавлением
    status, status_code = await check_site(url)
    is_up = 1 if status else 0

    # Проверяем SSL сертификат, если сайт доступен и использует HTTPS
    ssl_info = None
    has_ssl = 0
    ssl_expires_at = None
    ssl_message = ""

    if status and url.startswith('https://'):
        await bot.edit_message_text(f"🔄 Проверяю SSL сертификат для {original_url}...",
                                    chat_id=message.chat.id,
                                    message_id=status_msg.message_id)
        ssl_info = await check_ssl_certificate(url)
        has_ssl = 1 if ssl_info.get('has_ssl', False) else 0

        if has_ssl:
            ssl_expires_at = ssl_info.get('expiry_date')
            days_left = ssl_info.get('days_left')

            if ssl_info.get('expired'):
                ssl_message = f"\n⚠️ SSL сертификат ИСТЁК!"
            elif ssl_info.get('expires_soon'):
                ssl_message = f"\n⚠️ SSL сертификат истекает через {days_left} дней!"
            else:
                ssl_message = f"\nSSL сертификат действителен ещё {days_left} дней."

            ssl_message += f"\nВыдан: {ssl_info.get('subject')}"
            ssl_message += f"\nЦентр сертификации: {ssl_info.get('issuer')}"
        else:
            ssl_message = "\n❌ SSL сертификат не найден или недействителен."

    # Записываем сайт в базу данных
    cursor.execute(
        "INSERT INTO sites (url, original_url, user_id, is_up, has_ssl, ssl_expires_at, last_check) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (url, original_url, message.from_user.id, is_up, has_ssl, ssl_expires_at, datetime.now())
    )
    conn.commit()
    conn.close()

    # Если URL был преобразован, показываем пользователю информацию о конвертации
    punycode_info = ""
    if url != original_url and "xn--" in url:
        punycode_info = f"\nПреобразовано в: {url}"

    if status:
        await bot.edit_message_text(
            f"✅ Сайт {original_url} добавлен в мониторинг и сейчас доступен (код ответа: {status_code}).{punycode_info}{ssl_message}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
    else:
        await bot.edit_message_text(
            f"⚠️ Сайт {original_url} добавлен в мониторинг, но сейчас НЕ доступен (код ответа: {status_code}).{punycode_info}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )

    await state.clear()


# Обработчик команды /list
@dp.message(Command("list"))
async def cmd_list(message: Message):
    conn = sqlite3.connect('sites_monitor.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, url, original_url, is_up, has_ssl, ssl_expires_at, last_check 
        FROM sites WHERE user_id = ?
    """, (message.from_user.id,))
    sites = cursor.fetchall()
    conn.close()

    if not sites:
        await message.answer("📝 Список отслеживаемых сайтов пуст. Добавьте сайт командой /add")
        return

    response = "📝 Список отслеживаемых сайтов:\n\n"
    for site_id, url, original_url, is_up, has_ssl, ssl_expires_at, last_check in sites:
        # Используем оригинальный URL для отображения, если он есть
        display_url = original_url if original_url else url
        status = "✅ доступен" if is_up else "❌ недоступен"
        last_check_str = "Еще не проверялся" if not last_check else datetime.fromisoformat(last_check).strftime(
            "%d.%m.%Y %H:%M:%S")

        site_info = f"ID: {site_id}\nURL: {display_url}\nСтатус: {status}\n"

        # Добавляем информацию о SSL сертификате
        if has_ssl and ssl_expires_at:
            expiry_date = datetime.fromisoformat(ssl_expires_at)
            days_left = (expiry_date - datetime.now()).days
            if days_left <= 0:
                ssl_status = "⚠️ SSL сертификат ИСТЁК!"
            elif days_left <= SSL_WARNING_DAYS:
                ssl_status = f"⚠️ SSL сертификат истекает через {days_left} дней"
            else:
                ssl_status = f"SSL действителен ещё {days_left} дней"
            site_info += f"{ssl_status}\n"
        elif url.startswith('https://'):
            site_info += "❌ SSL сертификат не проверен\n"

        site_info += f"Последняя проверка: {last_check_str}\n\n"
        response += site_info

    await message.answer(response)


# Обработчик команды /remove
@dp.message(Command("remove"))
async def cmd_remove(message: Message):
    # Проверяем есть ли аргументы у команды
    command_parts = message.text.split(maxsplit=1)
    args = command_parts[1] if len(command_parts) > 1 else None

    if not args:
        conn = sqlite3.connect('sites_monitor.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, original_url, url FROM sites WHERE user_id = ?", (message.from_user.id,))
        sites = cursor.fetchall()
        conn.close()

        if not sites:
            await message.answer("📝 Список отслеживаемых сайтов пуст.")
            return

        response = "Для удаления сайта используйте команду /remove ID\n\nСписок ваших сайтов:\n"
        for site_id, original_url, url in sites:
            display_url = original_url if original_url else url
            response += f"ID: {site_id} - {display_url}\n"

        await message.answer(response)
        return

    try:
        site_id = int(args)
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    conn = sqlite3.connect('sites_monitor.db')
    cursor = conn.cursor()
    cursor.execute("SELECT original_url, url FROM sites WHERE id = ? AND user_id = ?", (site_id, message.from_user.id))
    site = cursor.fetchone()

    if not site:
        await message.answer(f"❌ Сайт с ID {site_id} не найден или не принадлежит вам.")
    else:
        original_url, url = site
        display_url = original_url if original_url else url
        cursor.execute("DELETE FROM sites WHERE id = ? AND user_id = ?", (site_id, message.from_user.id))
        conn.commit()
        await message.answer(f"✅ Сайт {display_url} удален из мониторинга.")

    conn.close()


# Обработчик команды /status
@dp.message(Command("status"))
async def cmd_status(message: Message):
    conn = sqlite3.connect('sites_monitor.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, original_url FROM sites WHERE user_id = ?", (message.from_user.id,))
    sites = cursor.fetchall()
    conn.close()

    if not sites:
        await message.answer("📝 Список отслеживаемых сайтов пуст. Добавьте сайт командой /add")
        return

    msg = await message.answer("🔄 Проверяю доступность сайтов...")

    results = []
    for site_id, url, original_url in sites:
        display_url = original_url if original_url else url

        # Проверяем доступность сайта
        status, status_code = await check_site(url)
        status_str = f"✅ доступен (код {status_code})" if status else f"❌ недоступен (код {status_code})"
        site_info = f"ID: {site_id}\nURL: {display_url}\nСтатус: {status_str}"

        # Проверяем SSL сертификат, если сайт доступен и использует HTTPS
        ssl_info = None
        has_ssl = False
        ssl_expires_at = None

        if status and url.startswith('https://'):
            ssl_info = await check_ssl_certificate(url)
            has_ssl = ssl_info.get('has_ssl', False)

            if has_ssl:
                expiry_date = ssl_info.get('expiry_date')
                days_left = ssl_info.get('days_left')

                if ssl_info.get('expired'):
                    site_info += f"\n⚠️ SSL сертификат ИСТЁК!"
                elif ssl_info.get('expires_soon'):
                    site_info += f"\n⚠️ SSL сертификат истекает через {days_left} дней!"
                else:
                    site_info += f"\nSSL действителен ещё {days_left} дней"

                ssl_expires_at = expiry_date
            else:
                site_info += "\n❌ SSL сертификат не найден или недействителен"

        results.append(site_info)

        # Обновляем статус в БД
        conn = sqlite3.connect('sites_monitor.db')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sites SET is_up = ?, has_ssl = ?, ssl_expires_at = ?, last_check = ? WHERE id = ?",
            (1 if status else 0, 1 if has_ssl else 0, ssl_expires_at, datetime.now(), site_id)
        )
        conn.commit()
        conn.close()

    response = "📊 Результаты проверки:\n\n" + "\n\n".join(results)
    await bot.edit_message_text(response, chat_id=message.chat.id, message_id=msg.message_id)


# Функция проверки доступности сайта
async def check_site(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                return response.status < 400, response.status
    except Exception:
        return False, 0


# Функция периодической проверки всех сайтов
async def scheduled_check():
    while True:
        try:
            conn = sqlite3.connect('sites_monitor.db')
            cursor = conn.cursor()
            cursor.execute("SELECT id, url, original_url, user_id, is_up, has_ssl, ssl_expires_at FROM sites")
            sites = cursor.fetchall()

            for site_id, url, original_url, user_id, was_up, had_ssl, old_ssl_expires_at in sites:
                display_url = original_url if original_url else url
                now = datetime.now()

                # Проверяем доступность
                status, status_code = await check_site(url)
                status_changed = status != bool(was_up)

                # Проверяем SSL, если сайт доступен и использует HTTPS
                ssl_info = None
                has_ssl = False
                ssl_expires_at = old_ssl_expires_at
                ssl_changed = False
                ssl_warning = False

                if status and url.startswith('https://'):
                    ssl_info = await check_ssl_certificate(url)
                    has_ssl = ssl_info.get('has_ssl', False)
                    ssl_changed = has_ssl != bool(had_ssl)

                    if has_ssl:
                        ssl_expires_at = ssl_info.get('expiry_date')

                        # Проверяем, нужно ли отправить предупреждение о скором истечении сертификата
                        if ssl_info.get('expires_soon') or ssl_info.get('expired'):
                            # Если старых данных не было или дата изменилась
                            if not old_ssl_expires_at or str(ssl_expires_at) != old_ssl_expires_at:
                                ssl_warning = True

                # Обновляем статус в БД
                cursor.execute(
                    "UPDATE sites SET is_up = ?, has_ssl = ?, ssl_expires_at = ?, last_check = ? WHERE id = ?",
                    (1 if status else 0, 1 if has_ssl else 0, ssl_expires_at, now, site_id)
                )

                # Отправляем уведомления при изменении статуса
                try:
                    # Уведомление об изменении доступности
                    if status_changed:
                        if status:
                            message = f"✅ Сайт снова доступен!\nURL: {display_url}\nКод ответа: {status_code}\nВремя: {now.strftime('%d.%m.%Y %H:%M:%S')}"
                        else:
                            message = f"❌ Сайт стал недоступен!\nURL: {display_url}\nКод ответа: {status_code}\nВремя: {now.strftime('%d.%m.%Y %H:%M:%S')}"
                        await bot.send_message(chat_id=user_id, text=message)

                    # Уведомление об изменении SSL
                    if ssl_changed and has_ssl:
                        days_left = ssl_info.get('days_left')
                        message = f"🔒 Обнаружен SSL сертификат для {display_url}\nДействителен до: {ssl_expires_at.strftime('%d.%m.%Y')}\n"
                        if ssl_info.get('expired'):
                            message += "⚠️ Сертификат ИСТЁК! Требуется обновление."
                        elif ssl_info.get('expires_soon'):
                            message += f"⚠️ Сертификат истекает через {days_left} дней!"
                        await bot.send_message(chat_id=user_id, text=message)

                    # Уведомление о скором истечении SSL
                    elif ssl_warning and has_ssl:
                        days_left = ssl_info.get('days_left')
                        if ssl_info.get('expired'):
                            message = f"⚠️ SSL сертификат для {display_url} ИСТЁК!\nТребуется немедленное обновление."
                        else:
                            message = f"⚠️ SSL сертификат для {display_url} истекает через {days_left} дней!\nРекомендуется обновить сертификат."
                        await bot.send_message(chat_id=user_id, text=message)

                except Exception as e:
                    logging.error(f"Error sending notification to user {user_id}: {e}")

            conn.commit()
            conn.close()

        except Exception as e:
            logging.error(f"Error in scheduled check: {e}")

        # Ждем определенное время перед следующей проверкой
        await asyncio.sleep(CHECK_INTERVAL)


# Запуск периодической проверки как фоновую задачу
async def on_startup():
    asyncio.create_task(scheduled_check())


async def main():
    init_db()
    update_db()  # Add this line
    # Запускаем задачу проверки сайтов при старте
    await on_startup()
    # Запуск бота
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())