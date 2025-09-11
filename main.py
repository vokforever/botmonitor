import asyncio
import aiohttp
import logging
import idna  # для работы с Punycode
import ssl
import socket
import OpenSSL
import os
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.command import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from dotenv import load_dotenv
from supabase import create_client, Client

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота (загружаем токен из переменных окружения)
API_TOKEN = os.getenv('API_TOKEN')
if not API_TOKEN:
    raise ValueError("API_TOKEN не найден в переменных окружения. Создайте .env файл с API_TOKEN=your_token")

# ID чата администратора для уведомлений
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID не найден в переменных окружения. Создайте .env файл с ADMIN_CHAT_ID=your_chat_id")

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL и SUPABASE_KEY не найдены в переменных окружения")

# ScreenshotMachine API ключ (опционально)
SCREENSHOTMACHINE_API_KEY = os.getenv('SCREENSHOTMACHINE_API_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

from io import BytesIO
import requests

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Интервал проверки в секундах
CHECK_INTERVAL = 300  # 5 минут
SSL_WARNING_DAYS = 30  # Предупреждение о сроке истечения SSL сертификата (в днях)




async def is_admin_in_chat(chat_id: int, user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False




async def send_admin_notification(message: str):
    """Отправляет уведомление администратору"""
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        logging.info(f"Уведомление отправлено админу: {message}")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления админу: {e}")

async def safe_send_message(chat_id: int, text: str, parse_mode: str = None, max_retries: int = 3):
    """Безопасная отправка сообщения с retry механизмом"""
    for attempt in range(max_retries):
        try:
            if parse_mode:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
            else:
                await bot.send_message(chat_id=chat_id, text=text)
            return True
        except TelegramRetryAfter as e:
            logging.warning(f"Rate limit hit, waiting {e.retry_after} seconds...")
            await asyncio.sleep(e.retry_after)
        except TelegramNetworkError as e:
            logging.warning(f"Network error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logging.error(f"Failed to send message after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error sending message: {e}")
            return False
    return False

async def safe_reply_message(message: Message, text: str, parse_mode: str = None, max_retries: int = 3):
    """Безопасный ответ на сообщение с retry механизмом"""
    for attempt in range(max_retries):
        try:
            if parse_mode:
                await message.reply(text, parse_mode=parse_mode)
            else:
                await message.reply(text)
            return True
        except TelegramRetryAfter as e:
            logging.warning(f"Rate limit hit, waiting {e.retry_after} seconds...")
            await asyncio.sleep(e.retry_after)
        except TelegramNetworkError as e:
            logging.warning(f"Network error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logging.error(f"Failed to reply to message after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error replying to message: {e}")
            return False
    return False


def get_sites_count():
    """Возвращает количество сайтов в базе данных"""
    try:
        result = supabase.table('botmonitor_sites').select('id', count='exact').execute()
        return result.count
    except Exception as e:
        logging.error(f"Ошибка получения количества сайтов: {e}")
        return 0

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
                    # FIX: Make expiry_date timezone-aware (UTC)
                    expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                    issuer = dict(x509.get_issuer().get_components())
                    issuer_name = issuer.get(b'CN', b'Unknown').decode('utf-8')
                    subject = dict(x509.get_subject().get_components())
                    subject_name = subject.get(b'CN', b'Unknown').decode('utf-8')

                    days_left = (expiry_date - datetime.now(timezone.utc)).days

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


async def take_screenshot(url: str) -> BytesIO:
    """Создание скриншота через ScreenshotMachine API"""
    if not SCREENSHOTMACHINE_API_KEY:
        logging.error("ScreenshotMachine API key not provided")
        return None
    
    try:
        logging.info(f"Creating screenshot via ScreenshotMachine API for URL: {url}")
        
        # Параметры для ScreenshotMachine API
        params = {
            'key': SCREENSHOTMACHINE_API_KEY,
            'url': url,
            'dimension': '1920x1080',  # Высокое разрешение
            'format': 'PNG',
            'cacheLimit': 0,  # Не кэшировать
            'timeout': 30,    # 30 секунд таймаут
            'device': 'desktop',
            'fullPage': 'false',
            'thumbnail': 'false'
        }
        
        # Отправляем запрос к API
        response = requests.get('https://api.screenshotmachine.com', params=params, timeout=35)
        
        if response.status_code == 200:
            logging.info(f"Screenshot created successfully via API for {url}")
            return BytesIO(response.content)
        else:
            logging.error(f"ScreenshotMachine API error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logging.error(f"Timeout while creating screenshot via API for {url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error while creating screenshot via API for {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error while creating screenshot via API for {url}: {e}")
        return None


async def diagnose_api():
    """Диагностическая функция для проверки работы ScreenshotMachine API"""
    try:
        logging.info("Starting ScreenshotMachine API diagnosis...")
        
        if not SCREENSHOTMACHINE_API_KEY:
            logging.error("ScreenshotMachine API key not provided")
            return False
        
        # Тестируем API с простым запросом
        test_url = "https://httpbin.org/get"
        params = {
            'key': SCREENSHOTMACHINE_API_KEY,
            'url': test_url,
            'dimension': '1024x768',
            'format': 'PNG',
            'cacheLimit': 0,
            'timeout': 10
        }
        
        response = requests.get('https://api.screenshotmachine.com', params=params, timeout=15)
        
        if response.status_code == 200:
            logging.info("ScreenshotMachine API is working correctly")
            logging.info(f"API response size: {len(response.content)} bytes")
            return True
        else:
            logging.error(f"ScreenshotMachine API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"ScreenshotMachine API diagnosis failed: {e}")
        return False


# Настройка базы данных
def init_db():
    # Таблица создается через SQL в Supabase Dashboard
    pass


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
        "/help - показать справку\n"
        "/screenshot ID - сделать скриншот сайта\n"
        "/diagnose - диагностика ScreenshotMachine API"
    )


# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = "ℹ️ Справка по командам:\n\n"
    
    if message.chat.type in ['group', 'supergroup']:
        help_text += "**В группах:**\n"
        help_text += "@бот - показать статус всех сайтов в этом чате\n"
        help_text += "@бот домен.com - показать информацию о конкретном сайте\n\n"
    
    help_text += "**Команды:**\n"
    help_text += "/add [URL] - добавить новый сайт для мониторинга\n"
    help_text += "/list - показать список всех отслеживаемых сайтов\n"
    help_text += "/remove [ID] - удалить сайт из мониторинга\n"
    help_text += "/status - выполнить проверку статуса всех сайтов\n"
    help_text += "/screenshot [ID] - сделать скриншот сайта\n"
    help_text += "/diagnose - диагностика ScreenshotMachine API\n"
    help_text += "/help - показать эту справку\n\n"
    help_text += "**Особенности:**\n"
    help_text += "• Бот автоматически проверяет сайты каждые 5 минут\n"
    help_text += "• Поддержка кириллических доменов (цифровизируем.рф)\n"
    help_text += "• Автоматическое добавление протокола http:// или https://\n"
    help_text += "• Проверка SSL сертификатов для HTTPS сайтов"
    
    await message.answer(help_text, parse_mode="Markdown")


# Обработчик команды /add
@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    # Проверка прав для групп
    if message.chat.type in ['group', 'supergroup']:
        if not await is_admin_in_chat(message.chat.id, message.from_user.id):
            await message.answer("Только администраторы могут добавлять сайты для мониторинга в группе.")
            return

    # Извлекаем URL, если он передан вместе с командой
    command_parts = message.text.split(maxsplit=1)
    url_from_args = command_parts[1] if len(command_parts) > 1 else None

    if url_from_args:
        # Если URL передан, сразу обрабатываем его
        await process_and_add_site(url_from_args, message, state)
    else:
        # Если URL не передан, запрашиваем его как раньше
        await state.set_state(AddSite.waiting_for_url)
        await message.answer("Отправьте URL сайта, который хотите мониторить.\nНапример: example.com или цифровизируем.рф")

# Получение URL для добавления (когда пользователь отправляет его после запроса)
@dp.message(AddSite.waiting_for_url)
async def process_url_input(message: Message, state: FSMContext):
    # Используем новую функцию для обработки
    await process_and_add_site(message.text, message, state)

# НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ для добавления сайта (чтобы не дублировать код)
async def process_and_add_site(original_url: str, message: Message, state: FSMContext):
    url = process_url(original_url)
    # Проверка, существует ли уже такой URL для этого пользователя
    existing = supabase.table('botmonitor_sites').select('id').eq('url', url).eq('chat_id', message.chat.id).execute()
    if existing.data:
        await message.answer(f"⚠️ Сайт {original_url} уже добавлен в мониторинг.")
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
            # Используем .get для безопасного извлечения данных
            subject_name = ssl_info.get('subject', 'N/A')
            issuer_name = ssl_info.get('issuer', 'N/A')
            ssl_message += f"\nВыдан: {subject_name}"
            ssl_message += f"\nЦентр сертификации: {issuer_name}"
        else:
            ssl_message = "\n❌ SSL сертификат не найден или недействителен."
            
    # Записываем сайт в базу данных
    supabase.table('botmonitor_sites').insert({
        'url': url,
        'original_url': original_url,
        'user_id': message.from_user.id,
        'chat_id': message.chat.id,
        'chat_type': message.chat.type,
        'is_up': is_up,
        'has_ssl': has_ssl,
        'ssl_expires_at': ssl_expires_at.isoformat() if ssl_expires_at else None,
        'last_check': datetime.now(timezone.utc).isoformat()
    }).execute()
    
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
    sites_data = supabase.table('botmonitor_sites').select('id, url, original_url, is_up, has_ssl, ssl_expires_at, last_check').eq('chat_id', message.chat.id).execute()
    sites = [(s['id'], s['url'], s['original_url'], s['is_up'], s['has_ssl'], s['ssl_expires_at'], s['last_check']) for s in sites_data.data]

    if not sites:
        await message.answer("📝 Список отслеживаемых сайтов пуст. Добавьте сайт командой /add")
        return

    response = "📝 Список отслеживаемых сайтов:\n\n"
    for site_id, url, original_url, is_up, has_ssl, ssl_expires_at, last_check in sites:
        # Используем оригинальный URL для отображения, если он есть
        display_url = original_url if original_url else url
        status = "✅ доступен" if is_up else "❌ недоступен"
        last_check_str = "Еще не проверялся" if not last_check else datetime.fromisoformat(last_check.replace('Z', '+00:00')).strftime("%d.%m.%Y %H:%M:%S")

        site_info = f"ID: {site_id}\nURL: {display_url}\nСтатус: {status}\n"

        # Добавляем информацию о SSL сертификате
        if has_ssl and ssl_expires_at:
            expiry_date = datetime.fromisoformat(ssl_expires_at.replace('Z', '+00:00'))
            days_left = (expiry_date - datetime.now(timezone.utc)).days
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
        sites_data = supabase.table('botmonitor_sites').select('id, original_url, url').eq('chat_id', message.chat.id).execute()
        sites = [(s['id'], s['original_url'], s['url']) for s in sites_data.data]

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

    site_data = supabase.table('botmonitor_sites').select('original_url, url').eq('id', site_id).eq('chat_id', message.chat.id).execute()
    site = (site_data.data[0]['original_url'], site_data.data[0]['url']) if site_data.data else None

    if not site:
        await message.answer(f"❌ Сайт с ID {site_id} не найден или не принадлежит вам.")
    else:
        original_url, url = site
        display_url = original_url if original_url else url
        supabase.table('botmonitor_sites').delete().eq('id', site_id).eq('chat_id', message.chat.id).execute()
        await message.answer(f"✅ Сайт {display_url} удален из мониторинга.")


# Обработчик команды /status
@dp.message(Command("status"))
async def cmd_status(message: Message):
    sites_data = supabase.table('botmonitor_sites').select('id, url, original_url').eq('chat_id', message.chat.id).execute()
    sites = [(s['id'], s['url'], s['original_url']) for s in sites_data.data]

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
        supabase.table('botmonitor_sites').update({
            'is_up': status,
            'has_ssl': has_ssl,
            'ssl_expires_at': ssl_expires_at.isoformat() if ssl_expires_at else None,
            'last_check': datetime.now(timezone.utc).isoformat()
        }).eq('id', site_id).execute()

    response = "📊 Результаты проверки:\n\n" + "\n\n".join(results)
    await bot.edit_message_text(response, chat_id=message.chat.id, message_id=msg.message_id)


@dp.message(Command("screenshot"))
async def cmd_screenshot(message: Message):
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("Укажите ID сайта: /screenshot ID")
        return
    
    try:
        site_id = int(command_parts[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
        
    site_data = supabase.table('botmonitor_sites').select('url, original_url').eq('id', site_id).eq('chat_id', message.chat.id).execute()
    site = (site_data.data[0]['url'], site_data.data[0]['original_url']) if site_data.data else None
    
    if not site:
        await message.answer(f"Сайт с ID {site_id} не найден в этом чате.")
        return
        
    url, original_url = site
    display_url = original_url if original_url else url
    
    msg = await message.answer(f"Создаю скриншот для {display_url}...")
    
    screenshot = await take_screenshot(url)
    
    if screenshot:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=types.BufferedInputFile(screenshot.getvalue(), filename=f"screenshot_{site_id}.png"),
            caption=f"Скриншот сайта: {display_url}"
        )
        await bot.delete_message(message.chat.id, msg.message_id)
    else:
        await bot.edit_message_text("Ошибка создания скриншота. Проверьте API ключ ScreenshotMachine.", 
                                  chat_id=message.chat.id, message_id=msg.message_id)


@dp.message(Command("diagnose"))
async def cmd_diagnose(message: Message):
    """Команда диагностики ScreenshotMachine API"""
    # Проверка прав для групп
    if message.chat.type in ['group', 'supergroup']:
        if not await is_admin_in_chat(message.chat.id, message.from_user.id):
            await message.answer("Только администраторы могут запускать диагностику в группе.")
            return
    
    msg = await message.answer("🔍 Запускаю диагностику ScreenshotMachine API...")
    
    try:
        result = await diagnose_api()
        
        if result:
            await bot.edit_message_text(
                "✅ Диагностика ScreenshotMachine API завершена успешно!\n"
                "API работает корректно.",
                chat_id=message.chat.id,
                message_id=msg.message_id
            )
        else:
            await bot.edit_message_text(
                "❌ Диагностика ScreenshotMachine API завершилась с ошибками!\n"
                "Проверьте API ключ и логи для подробной информации.",
                chat_id=message.chat.id,
                message_id=msg.message_id
            )
    except Exception as e:
        await bot.edit_message_text(
            f"❌ Ошибка при выполнении диагностики: {str(e)}",
            chat_id=message.chat.id,
            message_id=msg.message_id
        )


# Обработчик упоминаний бота в группах
@dp.message(F.chat.type.in_(['group', 'supergroup']), F.text)
async def handle_group_mention(message: Message):
    # Проверяем, есть ли в сообщении упоминание бота
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    if f"@{bot_username}" not in message.text:
        # Это обычное сообщение, не для нашего бота, просто выходим
        return

    # Извлекаем домен из сообщения.
    # Удаляем упоминание бота и лишние пробелы
    cleaned_text = message.text.replace(f"@{bot_username}", "").strip()
    # Первое слово после упоминания считаем доменом
    domain = cleaned_text.split()[0] if cleaned_text and '.' in cleaned_text.split()[0] else None

    # --- НОВАЯ ЛОГИКА ---
    # Если домен указан, ищем информацию по конкретному сайту
    if domain:
        logging.info(f"Получен запрос для конкретного домена: {domain}")
        # Ищем этот сайт в базе данных для текущего чата
        sites_data = supabase.table('botmonitor_sites').select('id, url, original_url, is_up, has_ssl, ssl_expires_at, last_check').eq('chat_id', message.chat.id).execute()
        
        found_site = None
        for site in sites_data.data:
            # Проверяем совпадение с оригинальным или обработанным URL
            if domain in site.get('original_url', '') or domain in site.get('url', ''):
                found_site = site
                break
                
        if not found_site:
            await safe_reply_message(message, f"Сайт {domain} не найден в списке отслеживаемых для этого чата.")
            return

        # Формируем ответ с информацией о сайте
        site_id = found_site['id']
        site_url = found_site['url']
        original_url = found_site['original_url']
        is_up = found_site['is_up']
        has_ssl = found_site['has_ssl']
        ssl_expires_at = found_site['ssl_expires_at']
        last_check = found_site['last_check']
        
        display_url = original_url if original_url else site_url
        status = "✅ доступен" if is_up else "❌ недоступен"
        last_check_str = "Еще не проверялся" if not last_check else datetime.fromisoformat(last_check.replace('Z', '+00:00')).strftime("%d.%m.%Y %H:%M:%S")
        
        response_text = f"📊 **Информация о сайте:**\n\n" \
                        f"**ID:** `{site_id}`\n" \
                        f"**URL:** {display_url}\n" \
                        f"**Статус:** {status}\n"
        
        if has_ssl and ssl_expires_at:
            expiry_date = datetime.fromisoformat(ssl_expires_at.replace('Z', '+00:00'))
            days_left = (expiry_date - datetime.now(timezone.utc)).days
            if days_left <= 0:
                ssl_status = "⚠️ **SSL сертификат ИСТЁК!**"
            elif days_left <= SSL_WARNING_DAYS:
                ssl_status = f"⚠️ SSL сертификат истекает через {days_left} дней"
            else:
                ssl_status = f"✅ SSL действителен ещё {days_left} дней"
            response_text += f"**SSL:** {ssl_status}\n"
        elif site_url.startswith('https://'):
            response_text += "**SSL:** ❌ Сертификат не найден или недействителен\n"
        
        response_text += f"**Последняя проверка:** {last_check_str}"
        
        await safe_reply_message(message, response_text, parse_mode="Markdown")

    # Если домен НЕ указан, показываем статус всех сайтов в чате
    else:
        logging.info(f"Получен запрос на статус всех сайтов для чата {message.chat.id}")
        sites_data = supabase.table('botmonitor_sites').select('id, url, original_url').eq('chat_id', message.chat.id).execute()
        sites = [(s['id'], s['url'], s['original_url']) for s in sites_data.data]
        
        if not sites:
            await safe_reply_message(message, "📝 В этом чате нет сайтов для мониторинга. Добавьте сайт командой /add")
            return
            
        msg = await safe_reply_message(message, "🔄 Вы запросили статус всех сайтов. Начинаю проверку...")
        if not msg:
            return
            
        results = []
        for site_id, url, original_url in sites:
            display_url = original_url if original_url else url
            status, status_code = await check_site(url)
            status_str = f"✅ доступен (код {status_code})" if status else f"❌ недоступен (код {status_code})"
            site_info = f"**URL:** {display_url}\n**Статус:** {status_str}"

            ssl_expires_at = None
            has_ssl = False
            if status and url.startswith('https://'):
                ssl_info = await check_ssl_certificate(url)
                has_ssl = ssl_info.get('has_ssl', False)
                if has_ssl:
                    expiry_date = ssl_info.get('expiry_date')
                    days_left = ssl_info.get('days_left')
                    if ssl_info.get('expired'):
                        site_info += f"\n**SSL:** ⚠️ **ИСТЁК!**"
                    elif ssl_info.get('expires_soon'):
                        site_info += f"\n**SSL:** ⚠️ истекает через {days_left} дней!"
                    else:
                        site_info += f"\n**SSL:** ✅ действителен ещё {days_left} дней"
                    ssl_expires_at = expiry_date
                else:
                    site_info += "\n**SSL:** ❌ не найден или недействителен"
            results.append(site_info)
            
            # Обновляем статус в БД
            supabase.table('botmonitor_sites').update({
                'is_up': status,
                'has_ssl': has_ssl,
                'ssl_expires_at': ssl_expires_at.isoformat() if ssl_expires_at else None,
                'last_check': datetime.now(timezone.utc).isoformat()
            }).eq('id', site_id).execute()
            
        response = "📊 **Результаты проверки сайтов в этом чате:**\n\n" + "\n\n".join(results)
        await safe_send_message(message.chat.id, response, parse_mode="Markdown")


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
            sites_data = supabase.table('botmonitor_sites').select('id, url, original_url, user_id, chat_id, is_up, has_ssl, ssl_expires_at').execute()
            sites = [(s['id'], s['url'], s['original_url'], s['user_id'], s['chat_id'], s['is_up'], s['has_ssl'], s['ssl_expires_at']) for s in sites_data.data]

            for site_id, url, original_url, user_id, chat_id, was_up, had_ssl, old_ssl_expires_at in sites:
                display_url = original_url if original_url else url
                now = datetime.now(timezone.utc)

                # Проверяем доступность
                status, status_code = await check_site(url)
                status_changed = status != bool(was_up)

                # Проверяем SSL, если сайт доступен и использует HTTPS
                ssl_info = None
                has_ssl = False
                ssl_expires_at = old_ssl_expires_at
                ssl_changed = False
                ssl_warning = False
                
                # Обработка парсинга дат из Supabase
                if old_ssl_expires_at and isinstance(old_ssl_expires_at, str):
                    old_ssl_expires_at = datetime.fromisoformat(old_ssl_expires_at.replace('Z', '+00:00'))

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
                supabase.table('botmonitor_sites').update({
                    'is_up': status,
                    'has_ssl': has_ssl,
                    'ssl_expires_at': ssl_expires_at.isoformat() if ssl_expires_at and hasattr(ssl_expires_at, 'isoformat') else ssl_expires_at,
                    'last_check': now.isoformat()
                }).eq('id', site_id).execute()

                # Отправляем уведомления при изменении статуса
                try:
                    # Уведомление об изменении доступности
                    if status_changed:
                        if status:
                            message_text = f"✅ Сайт снова доступен!\nURL: {display_url}\nКод ответа: {status_code}\nВремя: {now.strftime('%d.%m.%Y %H:%M:%S')}"
                        else:
                            message_text = f"❌ Сайт стал недоступен!\nURL: {display_url}\nКод ответа: {status_code}\nВремя: {now.strftime('%d.%m.%Y %H:%M:%S')}"
                        await safe_send_message(chat_id=chat_id, text=message_text)

                    # Уведомление об изменении SSL
                    if ssl_changed and has_ssl:
                        days_left = ssl_info.get('days_left')
                        message_text = f"🔒 Обнаружен SSL сертификат для {display_url}\nДействителен до: {ssl_expires_at.strftime('%d.%m.%Y')}\n"
                        if ssl_info.get('expired'):
                            message_text += "⚠️ Сертификат ИСТЁК! Требуется обновление."
                        elif ssl_info.get('expires_soon'):
                            message_text += f"⚠️ Сертификат истекает через {days_left} дней!"
                        await safe_send_message(chat_id=chat_id, text=message_text)

                    # Уведомление о скором истечении SSL
                    elif ssl_warning and has_ssl:
                        days_left = ssl_info.get('days_left')
                        if ssl_info.get('expired'):
                            message_text = f"⚠️ SSL сертификат для {display_url} ИСТЁК!\nТребуется немедленное обновление."
                        else:
                            message_text = f"⚠️ SSL сертификат для {display_url} истекает через {days_left} дней!\nРекомендуется обновить сертификат."
                        await safe_send_message(chat_id=chat_id, text=message_text)

                except Exception as e:
                    logging.error(f"Error sending notification to chat {chat_id}: {e}")


        except Exception as e:
            logging.error(f"Error in scheduled check: {e}")

        # Ждем определенное время перед следующей проверкой
        await asyncio.sleep(CHECK_INTERVAL)


# Запуск периодической проверки как фоновую задачу
async def on_startup():
    asyncio.create_task(scheduled_check())


async def main():
    init_db()
    
    # Получаем количество сайтов в базе данных
    sites_count = get_sites_count()
    
    # Запускаем диагностику API при старте
    logging.info("Running ScreenshotMachine API diagnosis on startup...")
    api_ok = await diagnose_api()
    
    # Отправляем уведомление админу о запуске
    startup_message = "🚀 Бот мониторинга сайтов запущен!\n" \
                     f"⏰ Время запуска: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n" \
                     f"🔄 Интервал проверки: {CHECK_INTERVAL // 60} минут\n" \
                     f"📊 Сайтов в базе проверки: {sites_count}\n" \
                     f"📸 ScreenshotMachine API: {'✅ OK' if api_ok else '❌ Ошибка'}"
    await send_admin_notification(startup_message)
    
    # Запускаем задачу проверки сайтов при старте
    await on_startup()
    # Запуск бота
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())