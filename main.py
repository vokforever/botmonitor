import asyncio
import aiohttp
import logging
import idna  # для работы с Punycode
import ssl
import socket
import OpenSSL
import os
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.command import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
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

# Новая переменная для управления уведомлениями
# os.getenv вернет строку 'True' или 'False', сравниваем ее
ONLY_ADMIN_PUSH = os.getenv('ONLY_ADMIN_PUSH') == 'True'

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
SSL_WARNING_DAYS = 30  # Предупреждение о сроке истечения SSL сертификата (в днях) - используется для отображения в списке

# Параметры для повторных проверок перед отправкой уведомления о недоступности
# Можно настроить через переменные окружения
DOWN_CHECK_ATTEMPTS = int(os.getenv('DOWN_CHECK_ATTEMPTS', '3'))  # Количество попыток проверки при недоступности
DOWN_CHECK_INTERVAL = int(os.getenv('DOWN_CHECK_INTERVAL', '10'))  # Интервал между попытками в секундах
DNS_ERROR_MULTIPLIER = int(os.getenv('DNS_ERROR_MULTIPLIER', '2'))  # Множитель интервала при DNS-ошибках
ENABLE_ALTERNATIVE_CHECK = os.getenv('ENABLE_ALTERNATIVE_CHECK', 'True') == 'True'  # Включить альтернативные проверки




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

async def send_notification(chat_id: int, text: str):
    """
    Отправляет уведомление либо в исходный чат, либо админу,
    в зависимости от настройки ONLY_ADMIN_PUSH.
    """
    target_chat_id = ADMIN_CHAT_ID if ONLY_ADMIN_PUSH else chat_id
    
    # Если отправляем админу, добавим информацию об исходном чате для ясности
    if ONLY_ADMIN_PUSH and str(chat_id) != str(ADMIN_CHAT_ID):
         notification_text = f"🔔 Уведомление для чата ID: {chat_id}\n\n{text}"
    else:
         # Если отправляем в тот же чат, дополнительная информация не нужна
         notification_text = text

    try:
        await bot.send_message(chat_id=target_chat_id, text=notification_text)
        logging.info(f"Уведомление отправлено в чат {target_chat_id}")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления в чат {target_chat_id}: {e}")

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

def split_message(text: str, max_length: int = 4000) -> list:
    """Разбивает длинное сообщение на части для отправки в Telegram"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    lines = text.split('\n')
    current_part = ""
    
    for line in lines:
        # Если добавление строки превысит лимит, сохраняем текущую часть
        if len(current_part) + len(line) + 1 > max_length:
            if current_part:
                parts.append(current_part.strip())
                current_part = line
            else:
                # Если одна строка слишком длинная, обрезаем её
                parts.append(line[:max_length])
        else:
            if current_part:
                current_part += '\n' + line
            else:
                current_part = line
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts


def get_sites_count():
    """Возвращает количество сайтов в базе данных (исключая резервные домены)"""
    try:
        result = supabase.table('botmonitor_sites').select('id', count='exact').eq('is_reserve_domain', False).execute()
        return result.count
    except Exception as e:
        logging.error(f"Ошибка получения количества сайтов: {e}")
        return 0

def get_sites_by_chat_id_flexible(chat_id, select_fields='*'):
    """
    Функция для поиска записей по chat_id с учетом возможных типов данных.
    Сначала пробует найти по исходному типу, потом по строковому представлению.
    """
    try:
        # Сначала пробуем найти по исходному chat_id
        logging.info(f"Ищем записи для chat_id={chat_id} (тип: {type(chat_id)})")
        result = supabase.table('botmonitor_sites').select(select_fields).eq('chat_id', chat_id).execute()
        
        if result.data:
            logging.info(f"Найдено {len(result.data)} записей для chat_id={chat_id}")
            return result
        
        # Если не найдено, пробуем как строку
        chat_id_str = str(chat_id)
        logging.info(f"Записи не найдены, пробуем как строку: chat_id='{chat_id_str}'")
        result = supabase.table('botmonitor_sites').select(select_fields).eq('chat_id', chat_id_str).execute()
        
        if result.data:
            logging.info(f"Найдено {len(result.data)} записей для chat_id='{chat_id_str}' (строка)")
            return result
        
        # Если и как строка не найдено, пробуем как int (если исходный тип был строка)
        if isinstance(chat_id, str):
            try:
                chat_id_int = int(chat_id)
                logging.info(f"Пробуем как число: chat_id={chat_id_int}")
                result = supabase.table('botmonitor_sites').select(select_fields).eq('chat_id', chat_id_int).execute()
                
                if result.data:
                    logging.info(f"Найдено {len(result.data)} записей для chat_id={chat_id_int} (число)")
                    return result
            except ValueError:
                pass
        
        logging.warning(f"Не найдено записей для chat_id ни в одном формате: {chat_id}")
        return result  # Возвращаем пустой результат
        
    except Exception as e:
        logging.error(f"Ошибка в get_sites_by_chat_id_flexible: {e}")
        # Возвращаем пустой результат в случае ошибки
        class EmptyResult:
            def __init__(self):
                self.data = []
                self.count = 0
        return EmptyResult()

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

# Состояния для установки дат истечения
class SetExpiration(StatesGroup):
    waiting_for_domain_date = State()
    waiting_for_hosting_date = State()


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
        "/setdomain ID - установить дату истечения домена\n"
        "/sethosting ID - установить дату истечения хостинга\n"
        "/myid - показать ваш User ID и Chat ID\n"
        "/help - показать справку\n"
        "/screenshot ID/URL - сделать скриншот сайта\n"
        "/diagnose - диагностика ScreenshotMachine API"
    )


# Обработчик команды /help
@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    """Команда для получения USER_ID и CHAT_ID"""
    await message.answer(f"User ID: `{message.from_user.id}`\nChat ID: `{message.chat.id}`", parse_mode="Markdown")

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
    help_text += "/setdomain [ID] - установить дату истечения домена\n"
    help_text += "/sethosting [ID] - установить дату истечения хостинга\n"
    help_text += "/myid - показать ваш User ID и Chat ID\n"
    help_text += "/screenshot [ID/URL] - сделать скриншот сайта\n"
    help_text += "/diagnose - диагностика ScreenshotMachine API\n"
    help_text += "/help - показать эту справку\n\n"
    help_text += "**Особенности:**\n"
    help_text += "• Бот автоматически проверяет сайты каждые 5 минут\n"
    help_text += "• При недоступности сайта выполняется несколько проверок ({attempts} попыток с интервалом {interval} сек)\n".format(attempts=DOWN_CHECK_ATTEMPTS, interval=DOWN_CHECK_INTERVAL)
    help_text += "• Поддержка кириллических доменов (цифровизируем.рф)\n"
    help_text += "• Автоматическое добавление протокола http:// или https://\n"
    help_text += "• Проверка SSL сертификатов для HTTPS сайтов\n"
    help_text += "• Настраиваемые параметры через переменные окружения:\n"
    help_text += f"  - DOWN_CHECK_ATTEMPTS: {DOWN_CHECK_ATTEMPTS} (количество попыток)\n"
    help_text += f"  - DOWN_CHECK_INTERVAL: {DOWN_CHECK_INTERVAL} сек (интервал между попытками)\n"
    help_text += f"  - DNS_ERROR_MULTIPLIER: {DNS_ERROR_MULTIPLIER} (множитель интервала при DNS-ошибках)\n"
    help_text += f"  - ENABLE_ALTERNATIVE_CHECK: {ENABLE_ALTERNATIVE_CHECK} (альтернативные проверки)\n"
    help_text += "• Умная обработка временных DNS-сбоев для снижения ложных уведомлений"
    
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
# ФИНАЛЬНАЯ ВЕРСИЯ: "Перезапись" чата при добавлении
async def process_and_add_site(original_url: str, message: Message, state: FSMContext):
    await state.clear()
    url = process_url(original_url)

    # 1. Ищем сайт в базе данных по URL, независимо от chat_id
    existing_site_data = supabase.table('botmonitor_sites').select('id, chat_id').eq('url', url).limit(1).execute()
    existing_site = existing_site_data.data[0] if existing_site_data.data else None

    # Если сайт уже привязан к ЭТОМУ чату, ничего не делаем
    if existing_site and str(existing_site.get('chat_id')) == str(message.chat.id):
        await message.answer(f"✅ Сайт {original_url} уже отслеживается в этом чате.")
        return

    # --- Общая часть для проверки статуса ---
    status_msg_text = f"🔄 Проверяю доступность сайта {original_url}..."
    if existing_site:
        status_msg_text = f"🔄 Сайт {original_url} уже есть в базе. Перемещаю его в этот чат и проверяю статус..."
    
    status_msg = await message.answer(status_msg_text)
    
    status, status_code, _ = await check_site_with_retries(url)
    is_up = 1 if status else 0
    
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
        else:
            ssl_message = "\n❌ SSL сертификат не найден или недействителен."
    # --- Конец общей части ---

    punycode_info = ""
    if url != original_url and "xn--" in url:
        punycode_info = f"\nПреобразовано в: {url}"

    payload = {
        'user_id': message.from_user.id,
        'chat_id': message.chat.id,
        'chat_type': message.chat.type,
        'is_up': is_up,
        'has_ssl': has_ssl,
        'ssl_expires_at': ssl_expires_at.isoformat() if ssl_expires_at else None,
        'last_check': datetime.now(timezone.utc).isoformat()
    }

    if existing_site:
        # 2. САЙТ НАЙДЕН -> ВЫПОЛНЯЕМ UPDATE
        supabase.table('botmonitor_sites').update(payload).eq('id', existing_site['id']).execute()
        
        final_message = f"✅ Сайт {original_url} был **перемещен** в этот чат.\nТекущий статус: {'доступен' if status else 'недоступен'} (код {status_code}).{punycode_info}{ssl_message}"
        await bot.edit_message_text(final_message, chat_id=message.chat.id, message_id=status_msg.message_id)

    else:
        # 3. САЙТ НЕ НАЙДЕН -> ВЫПОЛНЯЕМ INSERT
        payload['url'] = url
        payload['original_url'] = original_url
        
        supabase.table('botmonitor_sites').insert(payload).execute()
        
        final_message = f"✅ Сайт {original_url} **добавлен** в мониторинг.\nСтатус: {'доступен' if status else 'недоступен'} (код {status_code}).{punycode_info}{ssl_message}"
        await bot.edit_message_text(final_message, chat_id=message.chat.id, message_id=status_msg.message_id)


# Обработчик команды /reserve - переключение статуса резервного домена
@dp.message(Command("reserve"))
async def cmd_reserve(message: Message):
    """Переключает статус резервного домена для сайта"""
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /reserve <ID_сайта>\nПример: /reserve 123")
        return
    
    try:
        site_id = int(args[1])
    except ValueError:
        await message.answer("ID сайта должен быть числом")
        return
    
    # Получаем информацию о сайте
    site_data = supabase.table('botmonitor_sites').select('id, original_url, is_reserve_domain').eq('id', site_id).eq('chat_id', message.chat.id).execute()
    
    if not site_data.data:
        await message.answer("Сайт с таким ID не найден в этом чате")
        return
    
    site = site_data.data[0]
    current_status = site.get('is_reserve_domain', False)
    new_status = not current_status
    
    # Обновляем статус
    supabase.table('botmonitor_sites').update({'is_reserve_domain': new_status}).eq('id', site_id).execute()
    
    status_text = "резервным" if new_status else "обычным"
    await message.answer(f"✅ Сайт {site['original_url']} теперь является {status_text} доменом")


# Обработчик команды /list
@dp.message(Command("list"))
async def cmd_list(message: Message):
    logging.info(f"Команда /list для чата {message.chat.id}, тип: {type(message.chat.id)}")
    
    # Используем гибкую функцию поиска
    sites_data = get_sites_by_chat_id_flexible(message.chat.id, 'id, url, original_url, is_up, has_ssl, ssl_expires_at, domain_expires_at, hosting_expires_at, last_check, is_reserve_domain')
    logging.info(f"Команда /list - результат: data_length={len(sites_data.data) if sites_data.data else 0}")
    
    sites = sites_data.data

    if not sites:
        # Дополнительная диагностика
        all_sites_data = supabase.table('botmonitor_sites').select('id, chat_id').limit(3).execute()
        logging.info(f"Команда /list - примеры записей в базе: {all_sites_data.data}")
        await message.answer("📝 Список отслеживаемых сайтов пуст. Добавьте сайт командой /add")
        return

    response = "📝 Список отслеживаемых сайтов:\n\n"
    for site in sites:
        site_id = site['id']
        url = site['url']
        original_url = site['original_url']
        is_up = site['is_up']
        has_ssl = site['has_ssl']
        ssl_expires_at = site['ssl_expires_at']
        domain_expires_at = site['domain_expires_at']
        hosting_expires_at = site['hosting_expires_at']
        last_check = site['last_check']
        
        # Используем оригинальный URL для отображения, если он есть
        display_url = original_url if original_url else url
        is_reserve = site.get('is_reserve_domain', False)
        
        if is_reserve:
            status = "🔄 резервный" if is_up else "⏸️ резервный (недоступен)"
        else:
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

        # Добавляем информацию о датах истечения домена и хостинга
        if domain_expires_at:
            domain_date = datetime.fromisoformat(domain_expires_at).date()
            domain_days_left = (domain_date - datetime.now(timezone.utc).date()).days
            if domain_days_left <= 0:
                domain_status = f"⚠️ Домен истёк! ({domain_date.strftime('%d.%m.%Y')})"
            elif domain_days_left <= 30:
                domain_status = f"⚠️ Домен истекает через {domain_days_left} дней ({domain_date.strftime('%d.%m.%Y')})"
            else:
                domain_status = f"Домен до {domain_date.strftime('%d.%m.%Y')}"
            site_info += f"Домен: {domain_status}\n"
        else:
            site_info += "Домен: дата не установлена\n"

        if hosting_expires_at:
            hosting_date = datetime.fromisoformat(hosting_expires_at).date()
            hosting_days_left = (hosting_date - datetime.now(timezone.utc).date()).days
            if hosting_days_left <= 0:
                hosting_status = f"⚠️ Хостинг истёк! ({hosting_date.strftime('%d.%m.%Y')})"
            elif hosting_days_left <= 30:
                hosting_status = f"⚠️ Хостинг истекает через {hosting_days_left} дней ({hosting_date.strftime('%d.%m.%Y')})"
            else:
                hosting_status = f"Хостинг до {hosting_date.strftime('%d.%m.%Y')}"
            site_info += f"Хостинг: {hosting_status}\n"
        else:
            site_info += "Хостинг: дата не установлена\n"

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
    logging.info(f"Команда /status для чата {message.chat.id}, тип: {type(message.chat.id)}")
    
    # Используем гибкую функцию поиска
    sites_data = get_sites_by_chat_id_flexible(message.chat.id, 'id, url, original_url')
    logging.info(f"Команда /status - результат: data_length={len(sites_data.data) if sites_data.data else 0}")
    
    sites = [(s['id'], s['url'], s['original_url']) for s in sites_data.data]

    if not sites:
        # Дополнительная диагностика
        all_sites_data = supabase.table('botmonitor_sites').select('id, chat_id').limit(3).execute()
        logging.info(f"Команда /status - примеры записей в базе: {all_sites_data.data}")
        await message.answer("📝 Список отслеживаемых сайтов пуст. Добавьте сайт командой /add")
        return

    msg = await message.answer("🔄 Проверяю доступность сайтов...")

    results = []
    for site_id, url, original_url in sites:
        display_url = original_url if original_url else url

        # Проверяем доступность сайта с несколькими попытками
        status, status_code, attempts = await check_site_with_retries(url)
        status_str = f"✅ доступен (код {status_code})" if status else f"❌ недоступен (код {status_code}, попыток: {attempts})"
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
        await message.answer("Укажите ID сайта или URL: /screenshot ID или /screenshot URL")
        return
    
    argument = command_parts[1].strip()
    
    # Проверяем, является ли аргумент числом (ID)
    try:
        site_id = int(argument)
        # Это ID - ищем сайт в базе данных
        site_data = supabase.table('botmonitor_sites').select('url, original_url').eq('id', site_id).eq('chat_id', message.chat.id).execute()
        site = (site_data.data[0]['url'], site_data.data[0]['original_url']) if site_data.data else None
        
        if not site:
            await message.answer(f"Сайт с ID {site_id} не найден в этом чате.")
            return
            
        url, original_url = site
        display_url = original_url if original_url else url
        filename_suffix = f"id_{site_id}"
        
    except ValueError:
        # Это не число - считаем это URL
        url = process_url(argument)
        display_url = argument  # Показываем оригинальный URL пользователю
        filename_suffix = "url_" + argument.replace("://", "_").replace("/", "_").replace(".", "_")
    
    msg = await message.answer(f"Создаю скриншот для {display_url}...")
    
    screenshot = await take_screenshot(url)
    
    if screenshot:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=types.BufferedInputFile(screenshot.getvalue(), filename=f"screenshot_{filename_suffix}.png"),
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


# Обработчик команды /setdomain
@dp.message(Command("setdomain"))
async def cmd_setdomain(message: Message, state: FSMContext):
    # Проверка прав для групп
    if message.chat.type in ['group', 'supergroup']:
        if not await is_admin_in_chat(message.chat.id, message.from_user.id):
            await message.answer("Только администраторы могут устанавливать даты истечения в группе.")
            return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("Укажите ID сайта: /setdomain ID")
        return
    
    try:
        site_id = int(command_parts[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    
    # Проверяем, существует ли сайт
    site_data = supabase.table('botmonitor_sites').select('id, original_url, url').eq('id', site_id).eq('chat_id', message.chat.id).execute()
    if not site_data.data:
        await message.answer(f"Сайт с ID {site_id} не найден в этом чате.")
        return
    
    site = site_data.data[0]
    display_url = site['original_url'] if site['original_url'] else site['url']
    
    # Сохраняем ID сайта в состоянии
    await state.update_data(site_id=site_id)
    await state.set_state(SetExpiration.waiting_for_domain_date)
    
    await message.answer(
        f"Установка даты истечения домена для сайта: {display_url}\n\n"
        "Отправьте дату в формате YYYY-MM-DD (например: 2024-12-31)\n"
        "Или отправьте 'отмена' для отмены операции."
    )


# Обработчик команды /sethosting
@dp.message(Command("sethosting"))
async def cmd_sethosting(message: Message, state: FSMContext):
    # Проверка прав для групп
    if message.chat.type in ['group', 'supergroup']:
        if not await is_admin_in_chat(message.chat.id, message.from_user.id):
            await message.answer("Только администраторы могут устанавливать даты истечения в группе.")
            return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer("Укажите ID сайта: /sethosting ID")
        return
    
    try:
        site_id = int(command_parts[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    
    # Проверяем, существует ли сайт
    site_data = supabase.table('botmonitor_sites').select('id, original_url, url').eq('id', site_id).eq('chat_id', message.chat.id).execute()
    if not site_data.data:
        await message.answer(f"Сайт с ID {site_id} не найден в этом чате.")
        return
    
    site = site_data.data[0]
    display_url = site['original_url'] if site['original_url'] else site['url']
    
    # Сохраняем ID сайта в состоянии
    await state.update_data(site_id=site_id)
    await state.set_state(SetExpiration.waiting_for_hosting_date)
    
    await message.answer(
        f"Установка даты истечения хостинга для сайта: {display_url}\n\n"
        "Отправьте дату в формате YYYY-MM-DD (например: 2024-12-31)\n"
        "Или отправьте 'отмена' для отмены операции."
    )


# Обработчик ввода даты истечения домена
@dp.message(SetExpiration.waiting_for_domain_date)
async def process_domain_date_input(message: Message, state: FSMContext):
    if message.text.lower() == 'отмена':
        await state.clear()
        await message.answer("Операция отменена.")
        return
    
    try:
        # Парсим дату
        date_obj = datetime.strptime(message.text, '%Y-%m-%d').date()
        
        # Получаем ID сайта из состояния
        data = await state.get_data()
        site_id = data['site_id']
        
        # Обновляем дату в базе данных
        supabase.table('botmonitor_sites').update({
            'domain_expires_at': date_obj.isoformat()
        }).eq('id', site_id).execute()
        
        await message.answer(f"✅ Дата истечения домена установлена: {date_obj.strftime('%d.%m.%Y')}")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат YYYY-MM-DD (например: 2024-12-31)")


# Обработчик ввода даты истечения хостинга
@dp.message(SetExpiration.waiting_for_hosting_date)
async def process_hosting_date_input(message: Message, state: FSMContext):
    if message.text.lower() == 'отмена':
        await state.clear()
        await message.answer("Операция отменена.")
        return
    
    try:
        # Парсим дату
        date_obj = datetime.strptime(message.text, '%Y-%m-%d').date()
        
        # Получаем ID сайта из состояния
        data = await state.get_data()
        site_id = data['site_id']
        
        # Обновляем дату в базе данных
        supabase.table('botmonitor_sites').update({
            'hosting_expires_at': date_obj.isoformat()
        }).eq('id', site_id).execute()
        
        await message.answer(f"✅ Дата истечения хостинга установлена: {date_obj.strftime('%d.%m.%Y')}")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат YYYY-MM-DD (например: 2024-12-31)")


# Вспомогательные функции для обработки команд в группах
async def handle_screenshot_command(message: Message, args: str):
    """Обработка команды /screenshot в группе"""
    if not args:
        await safe_reply_message(message, "Укажите ID сайта или URL: @бот /screenshot ID или @бот /screenshot URL")
        return
    
    argument = args.strip()
    
    # Проверяем, является ли аргумент числом (ID)
    try:
        site_id = int(argument)
        # Это ID - ищем сайт в базе данных
        site_data = supabase.table('botmonitor_sites').select('url, original_url').eq('id', site_id).eq('chat_id', message.chat.id).execute()
        site = (site_data.data[0]['url'], site_data.data[0]['original_url']) if site_data.data else None
        
        if not site:
            await safe_reply_message(message, f"Сайт с ID {site_id} не найден в этом чате.")
            return
            
        url, original_url = site
        display_url = original_url if original_url else url
        filename_suffix = f"id_{site_id}"
        
    except ValueError:
        # Это не число - считаем это URL
        url = process_url(argument)
        display_url = argument  # Показываем оригинальный URL пользователю
        filename_suffix = "url_" + argument.replace("://", "_").replace("/", "_").replace(".", "_")
    
    msg = await safe_reply_message(message, f"Создаю скриншот для {display_url}...")
    
    screenshot = await take_screenshot(url)
    
    if screenshot:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=types.BufferedInputFile(screenshot.getvalue(), filename=f"screenshot_{filename_suffix}.png"),
            caption=f"Скриншот сайта: {display_url}"
        )
        if msg:
            await bot.delete_message(message.chat.id, msg.message_id)
    else:
        if msg:
            await bot.edit_message_text("Ошибка создания скриншота. Проверьте API ключ ScreenshotMachine.", 
                                      chat_id=message.chat.id, message_id=msg.message_id)

async def handle_status_command(message: Message):
    """Обработка команды /status в группе"""
    logging.info(f"handle_status_command для чата {message.chat.id}, тип: {type(message.chat.id)}")
    
    # Используем гибкую функцию поиска
    sites_data = get_sites_by_chat_id_flexible(message.chat.id, 'id, url, original_url')
    logging.info(f"handle_status_command - результат: data_length={len(sites_data.data) if sites_data.data else 0}")
    
    sites = [(s['id'], s['url'], s['original_url']) for s in sites_data.data]

    if not sites:
        # Дополнительная диагностика
        all_sites_data = supabase.table('botmonitor_sites').select('id, chat_id').limit(3).execute()
        logging.info(f"handle_status_command - примеры записей в базе: {all_sites_data.data}")
        await safe_reply_message(message, "📝 Список отслеживаемых сайтов пуст. Добавьте сайт командой /add")
        return

    msg = await safe_reply_message(message, "🔄 Проверяю доступность сайтов...")

    results = []
    for site_id, url, original_url in sites:
        display_url = original_url if original_url else url

        # Проверяем доступность сайта
        status, status_code, attempts = await check_site_with_retries(url)
        status_str = f"✅ доступен (код {status_code})" if status else f"❌ недоступен (код {status_code}, попыток: {attempts})"
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
    if msg:
        await bot.edit_message_text(response, chat_id=message.chat.id, message_id=msg.message_id)

async def handle_list_command(message: Message):
    """Обработка команды /list в группе"""
    logging.info(f"handle_list_command для чата {message.chat.id}, тип: {type(message.chat.id)}")
    
    # Используем гибкую функцию поиска
    sites_data = get_sites_by_chat_id_flexible(message.chat.id, 'id, url, original_url, is_up, has_ssl, ssl_expires_at, domain_expires_at, hosting_expires_at, last_check, is_reserve_domain')
    logging.info(f"handle_list_command - результат: data_length={len(sites_data.data) if sites_data.data else 0}")
    
    sites = sites_data.data

    if not sites:
        # Дополнительная диагностика
        all_sites_data = supabase.table('botmonitor_sites').select('id, chat_id').limit(3).execute()
        logging.info(f"handle_list_command - примеры записей в базе: {all_sites_data.data}")
        await safe_reply_message(message, "📝 Список отслеживаемых сайтов пуст. Добавьте сайт командой /add")
        return

    response = "📝 Список отслеживаемых сайтов:\n\n"
    for site in sites:
        site_id = site['id']
        url = site['url']
        original_url = site['original_url']
        is_up = site['is_up']
        has_ssl = site['has_ssl']
        ssl_expires_at = site['ssl_expires_at']
        domain_expires_at = site['domain_expires_at']
        hosting_expires_at = site['hosting_expires_at']
        last_check = site['last_check']
        
        # Используем оригинальный URL для отображения, если он есть
        display_url = original_url if original_url else url
        is_reserve = site.get('is_reserve_domain', False)
        
        if is_reserve:
            status = "🔄 резервный" if is_up else "⏸️ резервный (недоступен)"
        else:
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

        # Добавляем информацию о датах истечения домена и хостинга
        if domain_expires_at:
            domain_date = datetime.fromisoformat(domain_expires_at).date()
            domain_days_left = (domain_date - datetime.now(timezone.utc).date()).days
            if domain_days_left <= 0:
                domain_status = f"⚠️ Домен истёк! ({domain_date.strftime('%d.%m.%Y')})"
            elif domain_days_left <= 30:
                domain_status = f"⚠️ Домен истекает через {domain_days_left} дней ({domain_date.strftime('%d.%m.%Y')})"
            else:
                domain_status = f"Домен до {domain_date.strftime('%d.%m.%Y')}"
            site_info += f"Домен: {domain_status}\n"
        else:
            site_info += "Домен: дата не установлена\n"

        if hosting_expires_at:
            hosting_date = datetime.fromisoformat(hosting_expires_at).date()
            hosting_days_left = (hosting_date - datetime.now(timezone.utc).date()).days
            if hosting_days_left <= 0:
                hosting_status = f"⚠️ Хостинг истёк! ({hosting_date.strftime('%d.%m.%Y')})"
            elif hosting_days_left <= 30:
                hosting_status = f"⚠️ Хостинг истекает через {hosting_days_left} дней ({hosting_date.strftime('%d.%m.%Y')})"
            else:
                hosting_status = f"Хостинг до {hosting_date.strftime('%d.%m.%Y')}"
            site_info += f"Хостинг: {hosting_status}\n"
        else:
            site_info += "Хостинг: дата не установлена\n"

        site_info += f"Последняя проверка: {last_check_str}\n\n"
        response += site_info

    await safe_reply_message(message, response)


# Обработчик упоминаний бота в группах
@dp.message(F.chat.type.in_(['group', 'supergroup']), F.text)
async def handle_group_mention(message: Message):
    # Проверяем, есть ли в сообщении упоминание бота
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    if f"@{bot_username}" not in message.text:
        # Это обычное сообщение, не для нашего бота, просто выходим
        return

    # Извлекаем текст после упоминания бота
    cleaned_text = message.text.replace(f"@{bot_username}", "").strip()
    
    # Проверяем, является ли первое слово командой
    if cleaned_text.startswith('/'):
        # Это команда - обрабатываем её
        command_parts = cleaned_text.split(maxsplit=1)
        command = command_parts[0]
        args = command_parts[1] if len(command_parts) > 1 else ""
        
        if command == "/screenshot":
            # Обрабатываем команду /screenshot
            await handle_screenshot_command(message, args)
            return
        elif command == "/status":
            # Обрабатываем команду /status
            await handle_status_command(message)
            return
        elif command == "/list":
            # Обрабатываем команду /list
            await handle_list_command(message)
            return
        else:
            await safe_reply_message(message, f"Неизвестная команда: {command}")
            return
    
    # Если не команда, то ищем домен как раньше
    domain = cleaned_text.split()[0] if cleaned_text and '.' in cleaned_text.split()[0] else None

    # --- НОВАЯ ЛОГИКА ---
    # Если домен указан, ищем информацию по конкретному сайту
    if domain:
        logging.info(f"Получен запрос для конкретного домена: {domain}")
        # Ищем этот сайт в базе данных для текущего чата
        sites_data = get_sites_by_chat_id_flexible(message.chat.id, 'id, url, original_url, is_up, has_ssl, ssl_expires_at, domain_expires_at, hosting_expires_at, last_check')
        
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
        domain_expires_at = found_site['domain_expires_at']
        hosting_expires_at = found_site['hosting_expires_at']
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
        
        # Добавляем информацию о сроках окончания домена
        if domain_expires_at:
            domain_date = datetime.fromisoformat(domain_expires_at).date()
            domain_days_left = (domain_date - datetime.now(timezone.utc).date()).days
            if domain_days_left <= 0:
                domain_status = f"⚠️ **Домен истёк!** ({domain_date.strftime('%d.%m.%Y')})"
            elif domain_days_left <= 30:
                domain_status = f"⚠️ Домен истекает через {domain_days_left} дней ({domain_date.strftime('%d.%m.%Y')})"
            else:
                domain_status = f"✅ Домен до {domain_date.strftime('%d.%m.%Y')}"
            response_text += f"**Домен:** {domain_status}\n"
        else:
            response_text += "**Домен:** Дата не установлена\n"
        
        # Добавляем информацию о сроках окончания хостинга
        if hosting_expires_at:
            hosting_date = datetime.fromisoformat(hosting_expires_at).date()
            hosting_days_left = (hosting_date - datetime.now(timezone.utc).date()).days
            if hosting_days_left <= 0:
                hosting_status = f"⚠️ **Хостинг истёк!** ({hosting_date.strftime('%d.%m.%Y')})"
            elif hosting_days_left <= 30:
                hosting_status = f"⚠️ Хостинг истекает через {hosting_days_left} дней ({hosting_date.strftime('%d.%m.%Y')})"
            else:
                hosting_status = f"✅ Хостинг до {hosting_date.strftime('%d.%m.%Y')}"
            response_text += f"**Хостинг:** {hosting_status}\n"
        else:
            response_text += "**Хостинг:** Дата не установлена\n"
        
        response_text += f"**Последняя проверка:** {last_check_str}"
        
        await safe_reply_message(message, response_text, parse_mode="Markdown")

    # Если домен НЕ указан, показываем статус всех сайтов в чате
    else:
        logging.info(f"Получен запрос на статус всех сайтов для чата {message.chat.id}")
        logging.info(f"Тип chat_id: {type(message.chat.id)}, значение: {message.chat.id}")
        
        # Используем гибкую функцию поиска
        sites_data = get_sites_by_chat_id_flexible(message.chat.id, 'id, url, original_url, is_reserve_domain, domain_expires_at, hosting_expires_at')
        logging.info(f"Результат запроса к Supabase: count={sites_data.count if hasattr(sites_data, 'count') else 'N/A'}, data_length={len(sites_data.data) if sites_data.data else 0}")
        logging.info(f"Данные из Supabase: {sites_data.data[:2] if sites_data.data else 'Пустой результат'}")  # Показываем первые 2 записи для диагностики
        
        sites = [(s['id'], s['url'], s['original_url'], s.get('is_reserve_domain', False), s.get('domain_expires_at'), s.get('hosting_expires_at')) for s in sites_data.data]
        
        if not sites:
            logging.warning(f"Сайты для чата {message.chat.id} не найдены даже через гибкую функцию. Проверяем все записи в базе...")
            # Дополнительная диагностика - проверим все записи в таблице
            all_sites_data = supabase.table('botmonitor_sites').select('id, chat_id').limit(5).execute()
            logging.info(f"Примеры записей в базе (первые 5): {all_sites_data.data}")
            await safe_reply_message(message, "📝 В этом чате нет сайтов для мониторинга. Добавьте сайт командой /add")
            return
            
        # 1. СРАЗУ ОТПРАВЛЯЕМ ПРЕДВАРИТЕЛЬНЫЙ ОТВЕТ
        msg = await message.reply("🔄 Вы запросили статус всех сайтов. Начинаю проверку...")
        
        # 2. ВЫПОЛНЯЕМ ПРОВЕРКИ (МОЖЕТ ЗАНЯТЬ ВРЕМЯ)
        results = []
        
        # Проверяем, есть ли резервные домены в этом чате
        has_reserve_domains = any(site[3] for site in sites)  # site[3] это is_reserve_domain
        
        for site_id, url, original_url, is_reserve_domain, domain_expires_at, hosting_expires_at in sites:
            display_url = original_url if original_url else url
            
            # Для резервных доменов не проверяем доступность и не показываем их
            if is_reserve_domain:
                continue
            
            status, status_code, attempts = await check_site_with_retries(url)
            status_str = f"✅ доступен (код {status_code})" if status else f"❌ недоступен (код {status_code}, попыток: {attempts})"
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
            
            # Добавляем информацию о сроках окончания домена для всех сайтов
            if domain_expires_at:
                domain_date = datetime.fromisoformat(domain_expires_at).date()
                domain_days_left = (domain_date - datetime.now(timezone.utc).date()).days
                if domain_days_left <= 0:
                    domain_status = f"⚠️ **Домен истёк!** ({domain_date.strftime('%d.%m.%Y')})"
                elif domain_days_left <= 30:
                    domain_status = f"⚠️ Домен истекает через {domain_days_left} дней ({domain_date.strftime('%d.%m.%Y')})"
                else:
                    domain_status = f"✅ Домен до {domain_date.strftime('%d.%m.%Y')}"
                site_info += f"\n**Домен:** {domain_status}"
            else:
                site_info += "\n**Домен:** Дата не установлена"
            
            # Добавляем информацию о сроках окончания хостинга для всех сайтов
            if hosting_expires_at:
                hosting_date = datetime.fromisoformat(hosting_expires_at).date()
                hosting_days_left = (hosting_date - datetime.now(timezone.utc).date()).days
                if hosting_days_left <= 0:
                    hosting_status = f"⚠️ **Хостинг истёк!** ({hosting_date.strftime('%d.%m.%Y')})"
                elif hosting_days_left <= 30:
                    hosting_status = f"⚠️ Хостинг истекает через {hosting_days_left} дней ({hosting_date.strftime('%d.%m.%Y')})"
                else:
                    hosting_status = f"✅ Хостинг до {hosting_date.strftime('%d.%m.%Y')}"
                site_info += f"\n**Хостинг:** {hosting_status}"
            else:
                site_info += "\n**Хостинг:** Дата не установлена"
            
            results.append(site_info)
            
            # Обновляем статус в БД только для нерезервных доменов
            supabase.table('botmonitor_sites').update({
                'is_up': status,
                'has_ssl': has_ssl,
                'ssl_expires_at': ssl_expires_at.isoformat() if ssl_expires_at else None,
                'last_check': datetime.now(timezone.utc).isoformat()
            }).eq('id', site_id).execute()
            
        # 3. ОТПРАВЛЯЕМ РЕЗУЛЬТАТЫ (с разбивкой на части если нужно)
        response = "📊 **Результаты проверки сайтов в этом чате:**\n\n" + "\n\n".join(results)
        
        if has_reserve_domains:
            response += f"\n\n🔄 **Есть резервные домены** (нажмите кнопку ниже для просмотра)"
        
        # Удаляем исходное сообщение
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=msg.message_id)
        except Exception as e:
            logging.warning(f"Could not delete message: {e}")
        
        # Разбиваем сообщение на части и отправляем
        message_parts = split_message(response)
        keyboard = get_sites_keyboard() if has_reserve_domains else None
        
        for i, part in enumerate(message_parts):
            if i == 0:
                # Первое сообщение как ответ на исходное
                if keyboard and i == len(message_parts) - 1:
                    # Если это единственное сообщение и есть кнопка, добавляем её
                    await message.reply(part, parse_mode="Markdown", reply_markup=keyboard)
                else:
                    await safe_reply_message(message, part, parse_mode="Markdown")
            else:
                # Остальные как обычные сообщения
                if keyboard and i == len(message_parts) - 1:
                    # Если это последнее сообщение и есть кнопка, добавляем её
                    await bot.send_message(message.chat.id, part, parse_mode="Markdown", reply_markup=keyboard)
                else:
                    await safe_send_message(message.chat.id, part, parse_mode="Markdown")


# Функция проверки доступности сайта
async def check_site(url):
    """Базовая функция проверки доступности сайта"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                return response.status < 400, response.status
    except Exception as e:
        # Возвращаем информацию об ошибке для лучшей диагностики
        error_msg = str(e)
        if "No address associated with hostname" in error_msg or "Temporary failure in name resolution" in error_msg:
            logging.warning(f"DNS ошибка при проверке {url}: {error_msg}")
        return False, 0

async def check_site_alternative(url):
    """Альтернативная функция проверки через другой метод (для подтверждения)"""
    import subprocess
    import re
    
    try:
        # Извлекаем домен из URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Пробуем ping (только для подтверждения DNS-резолвинга)
        try:
            # Используем ping с таймаутом 5 секунд и 1 пакетом
            result = subprocess.run(['ping', '-c', '1', '-W', '5', domain],
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Ping прошел успешно, значит DNS работает
                logging.info(f"Альтернативная проверка {url}: ping успешен")
                return True, "ping_success"
            else:
                logging.warning(f"Альтернативная проверка {url}: ping неуспешен")
                return False, "ping_failed"
        except subprocess.TimeoutExpired:
            logging.warning(f"Альтернативная проверка {url}: ping таймаут")
            return False, "ping_timeout"
        except Exception as e:
            logging.warning(f"Альтернативная проверка {url}: ошибка ping - {e}")
            
        # Если ping не сработал, пробуем nslookup
        try:
            result = subprocess.run(['nslookup', domain],
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and "Address:" in result.stdout:
                logging.info(f"Альтернативная проверка {url}: DNS резолвинг успешен")
                return True, "dns_success"
            else:
                logging.warning(f"Альтернативная проверка {url}: DNS резолвинг неуспешен")
                return False, "dns_failed"
        except Exception as e:
            logging.warning(f"Альтернативная проверка {url}: ошибка nslookup - {e}")
            return False, "dns_error"
            
    except Exception as e:
        logging.error(f"Ошибка в альтернативной проверке {url}: {e}")
        return False, "error"

async def check_site_with_retries(url, max_attempts=DOWN_CHECK_ATTEMPTS, retry_interval=DOWN_CHECK_INTERVAL):
    """
    Улучшенная функция проверки доступности сайта с несколькими попытками.
    
    Args:
        url: URL сайта для проверки
        max_attempts: Максимальное количество попыток
        retry_interval: Интервал между попытками в секундах
    
    Returns:
        tuple: (is_available, status_code, attempts_made)
    """
    attempts = 0
    last_status_code = 0
    dns_errors_count = 0
    
    while attempts < max_attempts:
        attempts += 1
        is_available, status_code = await check_site(url)
        last_status_code = status_code
        
        # Если сайт доступен, возвращаем результат сразу
        if is_available:
            logging.info(f"Сайт {url} доступен с попытки {attempts} (статус: {status_code})")
            return True, status_code, attempts
        
        # Проверяем тип ошибки
        error_msg = str(status_code)  # В нашем случае 0 означает ошибку
        if status_code == 0:
            # Это ошибка подключения/DNS
            dns_errors_count += 1
            
            # Если это DNS-ошибка и у нас еще есть попытки, делаем дополнительную проверку
            if dns_errors_count >= 2 and attempts < max_attempts and ENABLE_ALTERNATIVE_CHECK:
                logging.info(f"Обнаружены множественные DNS-ошибки для {url}, выполняю альтернативную проверку...")
                alt_available, alt_result = await check_site_alternative(url)
                
                if alt_available:
                    logging.info(f"Альтернативная проверка подтвердила доступность {url} ({alt_result})")
                    return True, 200, attempts
                else:
                    logging.warning(f"Альтернативная проверка подтвердила недоступность {url} ({alt_result})")
        
        # Если сайт недоступен и это не последняя попытка, ждем перед следующей проверкой
        if attempts < max_attempts:
            # Увеличиваем интервал между попытками при DNS-ошибках
            current_interval = retry_interval * (DNS_ERROR_MULTIPLIER if dns_errors_count > 0 else 1)
            logging.info(f"Сайт {url} недоступен (статус: {status_code}), попытка {attempts}/{max_attempts}, повторная проверка через {current_interval} сек")
            await asyncio.sleep(current_interval)
    
    # Если все попытки неудачны
    logging.warning(f"Сайт {url} недоступен после {attempts} попыток (последний статус: {last_status_code}, DNS-ошибок: {dns_errors_count})")
    return False, last_status_code, attempts


# --- НОВЫЙ БЛОК: Данные для массового импорта ---

SITES_FOR_IMPORT = [
    # Даты в формате 'ГГГГ-ММ-ДД'. None означает NULL в базе данных.
    
    # Домены с датой истечения домена 30.03.2026
    {'url': 'https://прогрэсс.рф', 'original_url': 'прогрэсс.рф', 'domain_expires_at': '2026-03-30', 'hosting_expires_at': None},
    {'url': 'https://прогрэс.рф', 'original_url': 'прогрэс.рф', 'domain_expires_at': '2026-03-30', 'hosting_expires_at': None},
    {'url': 'https://про-гресс.рф', 'original_url': 'про-гресс.рф', 'domain_expires_at': '2026-03-30', 'hosting_expires_at': None},
    {'url': 'https://жкпрогресс.рф', 'original_url': 'жкпрогресс.рф', 'domain_expires_at': '2026-03-30', 'hosting_expires_at': None},

    # Домены с датой истечения домена 13.05.2026
    {'url': 'https://жкалькор.рф', 'original_url': 'жкалькор.рф', 'domain_expires_at': '2026-05-13', 'hosting_expires_at': None},
    {'url': 'https://жк-алькор.рф', 'original_url': 'жк-алькор.рф', 'domain_expires_at': '2026-05-13', 'hosting_expires_at': None},
    {'url': 'https://алькор82.рф', 'original_url': 'алькор82.рф', 'domain_expires_at': '2026-05-13', 'hosting_expires_at': None},
    {'url': 'https://jkalkor.ru', 'original_url': 'jkalkor.ru', 'domain_expires_at': '2026-05-13', 'hosting_expires_at': None},

    # Домены с датой истечения домена 27.04.2026
    {'url': 'https://progres82.ru', 'original_url': 'progres82.ru', 'domain_expires_at': '2026-04-27', 'hosting_expires_at': None},

    # Домены с датой истечения домена 03.05.2026
    {'url': 'https://миндаль.рус', 'original_url': 'миндаль.рус', 'domain_expires_at': '2026-05-03', 'hosting_expires_at': None},
    {'url': 'https://кварталминдаль.рф', 'original_url': 'кварталминдаль.рф', 'domain_expires_at': '2026-05-03', 'hosting_expires_at': None},
    {'url': 'https://квартал-миндаль.рф', 'original_url': 'квартал-миндаль.рф', 'domain_expires_at': '2026-05-03', 'hosting_expires_at': None},
    {'url': 'https://жк-миндаль.рф', 'original_url': 'жк-миндаль.рф', 'domain_expires_at': '2026-05-03', 'hosting_expires_at': None},
    {'url': 'https://kvartal-mindal.ru', 'original_url': 'kvartal-mindal.ru', 'domain_expires_at': '2026-05-03', 'hosting_expires_at': None},
    
    # Домены ТОЛЬКО с хостингом - 02.07.2026
    {'url': 'https://vladograd.com', 'original_url': 'vladograd.com', 'domain_expires_at': None, 'hosting_expires_at': '2026-07-02'},

    # Домен с доменом и хостингом - жигулинароща.рф
    {'url': 'https://жигулинароща.рф', 'original_url': 'жигулинароща.рф', 'domain_expires_at': '2026-06-03', 'hosting_expires_at': '2026-04-22'},

    # Дополнительные домены с датами истечения
    {'url': 'https://ccg-crimea.ru', 'original_url': 'ccg-crimea.ru', 'domain_expires_at': '2025-12-07', 'hosting_expires_at': None},

    # Домены с датой истечения 28.05.2026
    {'url': 'https://siesta-crimea.ru', 'original_url': 'siesta-crimea.ru', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://бархат-евпатория.рф', 'original_url': 'бархат-евпатория.рф', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://вега-крым.рф', 'original_url': 'вега-крым.рф', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://вега-евпатория.рф', 'original_url': 'вега-евпатория.рф', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://бархат-крым.рф', 'original_url': 'бархат-крым.рф', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://barhat-crimea.ru', 'original_url': 'barhat-crimea.ru', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://vega-crimea.ru', 'original_url': 'vega-crimea.ru', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://vega-evpatoria.ru', 'original_url': 'vega-evpatoria.ru', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://сиеста-крым.рф', 'original_url': 'сиеста-крым.рф', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://сиеста-новыйсвет.рф', 'original_url': 'сиеста-новыйсвет.рф', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://бархат-новыйсвет.рф', 'original_url': 'бархат-новыйсвет.рф', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},
    {'url': 'https://barhat-evpatoria.ru', 'original_url': 'barhat-evpatoria.ru', 'domain_expires_at': '2026-05-28', 'hosting_expires_at': None},

    # Домены с датой истечения 06.12.2025
    {'url': 'https://кварталпредгорье.рф', 'original_url': 'кварталпредгорье.рф', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},
    {'url': 'https://жкпредгорье.рус', 'original_url': 'жкпредгорье.рус', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},
    {'url': 'https://predgorie-crimea.ru', 'original_url': 'predgorie-crimea.ru', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},
    {'url': 'https://квартал-предгорье.рф', 'original_url': 'квартал-предгорье.рф', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},
    {'url': 'https://жк-предгорье.рф', 'original_url': 'жк-предгорье.рф', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},
    {'url': 'https://предгорье.рус', 'original_url': 'предгорье.рус', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},
    {'url': 'https://predgorie82.ru', 'original_url': 'predgorie82.ru', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},
    {'url': 'https://жкпредгорье.рф', 'original_url': 'жкпредгорье.рф', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': '2026-07-02'},
    {'url': 'https://predgorie.com', 'original_url': 'predgorie.com', 'domain_expires_at': '2025-12-06', 'hosting_expires_at': None},

    # Дополнительные домены с датами истечения
    {'url': 'https://moinaco-resort.ru', 'original_url': 'moinaco-resort.ru', 'domain_expires_at': '2026-03-20', 'hosting_expires_at': None},
    {'url': 'https://moinaco-riviera.ru', 'original_url': 'moinaco-riviera.ru', 'domain_expires_at': '2026-04-28', 'hosting_expires_at': None},

    # Домен с доменом и хостингом - moinaco.ru
    {'url': 'https://moinaco.ru', 'original_url': 'moinaco.ru', 'domain_expires_at': '2026-01-13', 'hosting_expires_at': '2027-06-21'},

    # Дополнительные домены с датами истечения
    {'url': 'https://modernatlas.ru', 'original_url': 'modernatlas.ru', 'domain_expires_at': '2025-09-20', 'hosting_expires_at': None},
    {'url': 'https://atlas-sudak.ru', 'original_url': 'atlas-sudak.ru', 'domain_expires_at': '2026-07-08', 'hosting_expires_at': None},
    {'url': 'https://atlassudak.com', 'original_url': 'atlassudak.com', 'domain_expires_at': '2026-06-13', 'hosting_expires_at': None},

    # Домен с доменом и хостингом - atlas-apart.ru
    {'url': 'https://atlas-apart.ru', 'original_url': 'atlas-apart.ru', 'domain_expires_at': '2025-09-11', 'hosting_expires_at': '2026-06-20'},

    # Дополнительные домены с датами истечения
    {'url': 'https://startprospect82.ru', 'original_url': 'startprospect82.ru', 'domain_expires_at': '2026-05-12', 'hosting_expires_at': None},
    {'url': 'https://startprospect82.online', 'original_url': 'startprospect82.online', 'domain_expires_at': '2026-05-12', 'hosting_expires_at': None},
    {'url': 'https://prospect-82.online', 'original_url': 'prospect-82.online', 'domain_expires_at': '2025-09-20', 'hosting_expires_at': None},
    {'url': 'https://prospect-82.ru', 'original_url': 'prospect-82.ru', 'domain_expires_at': '2025-09-20', 'hosting_expires_at': None},
    {'url': 'https://проспект-82.рф', 'original_url': 'проспект-82.рф', 'domain_expires_at': '2026-08-22', 'hosting_expires_at': None},

    # Домен с доменом и хостингом - prospect82.ru
    {'url': 'https://prospect82.ru', 'original_url': 'prospect82.ru', 'domain_expires_at': '2026-08-22', 'hosting_expires_at': '2025-09-14'},
]

# --- НОВЫЙ БЛОК: Создание клавиатуры и обработка нажатий ---

def get_renewal_keyboard(site_id: int, renewal_type: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками 'Продлён', 'Ещё не продлён' и 'Удалить'."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Продлён на год", callback_data=f"renew:{renewal_type}:{site_id}"),
            InlineKeyboardButton(text="OK", callback_data=f"snooze:{renewal_type}:{site_id}")
        ],
        [
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete:{renewal_type}:{site_id}")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_sites_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками для управления отображением сайтов."""
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Показать резервные домены", callback_data="show_reserve_domains")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

@dp.callback_query(F.data.startswith("renew:"))
async def handle_renew_callback(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку 'Продлён'."""
    try:
        _, renewal_type, site_id_str = callback.data.split(":")
        site_id = int(site_id_str)

        # Определяем, какое поле обновлять
        date_field = "domain_expires_at" if renewal_type == "domain" else "hosting_expires_at"

        # Безопасное получение текущей даты из БД
        success, site_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_sites').select(date_field).eq('id', site_id).single().execute()
        )
        
        if not success:
            logging.error(f"Не удалось получить данные сайта {site_id}: {site_result}")
            await callback.answer("Ошибка: не удалось получить данные сайта.", show_alert=True)
            return
        
        if not site_result.data or not site_result.data.get(date_field):
            await callback.answer("Ошибка: не найдена текущая дата для продления.", show_alert=True)
            return
        
        current_date = datetime.fromisoformat(site_result.data[date_field]).date()
        # Добавляем ровно 1 год
        new_date = current_date + relativedelta(years=1)

        # Безопасное обновление в БД
        update_success, update_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_sites').update({date_field: new_date.isoformat()}).eq('id', site_id).execute()
        )
        
        if not update_success:
            logging.error(f"Не удалось обновить дату для сайта {site_id}: {update_result}")
            await callback.answer("Ошибка: не удалось обновить дату.", show_alert=True)
            return

        # Отвечаем на callback и редактируем сообщение
        await callback.answer(f"Отлично! Срок обновлен до {new_date.strftime('%d.%m.%Y')}", show_alert=True)
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ **Статус обновлен.** Срок продлен до {new_date.strftime('%d.%m.%Y')}."
        )
    except Exception as e:
        logging.error(f"Ошибка в handle_renew_callback: {e}")
        await callback.answer("Произошла ошибка при обновлении.", show_alert=True)


@dp.callback_query(F.data.startswith("snooze:"))
async def handle_snooze_callback(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку 'Ещё не продлён' (просто убирает кнопки)."""
    await callback.answer("OK, принято.")
    await callback.message.edit_text(
        f"{callback.message.text}\n\n*OK, вы получили это уведомление.*"
    )

@dp.callback_query(F.data.startswith("delete:"))
async def handle_delete_callback(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку 'Удалить'."""
    try:
        _, renewal_type, site_id_str = callback.data.split(":")
        site_id = int(site_id_str)

        # Безопасное получение информации о сайте
        success, site_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_sites').select('original_url, url').eq('id', site_id).execute()
        )
        
        if not success or not site_result.data:
            logging.error(f"Не удалось получить данные сайта {site_id} для удаления: {site_result if not success else 'Сайт не найден'}")
            await callback.answer("Сайт не найден.", show_alert=True)
            return
        
        site = site_result.data[0]
        display_url = site['original_url'] if site['original_url'] else site['url']
        
        # Безопасное удаление сайта из базы данных
        delete_success, delete_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_sites').delete().eq('id', site_id).execute()
        )
        
        if not delete_success:
            logging.error(f"Не удалось удалить сайт {site_id}: {delete_result}")
            await callback.answer("Ошибка: не удалось удалить сайт.", show_alert=True)
            return
        
        # Отвечаем на callback и редактируем сообщение
        await callback.answer(f"Сайт {display_url} удален из мониторинга.", show_alert=True)
        await callback.message.edit_text(
            f"{callback.message.text}\n\n🗑️ **Сайт удален из мониторинга.**"
        )
    except Exception as e:
        logging.error(f"Ошибка в handle_delete_callback: {e}")
        await callback.answer("Произошла ошибка при удалении.", show_alert=True)

@dp.callback_query(F.data == "show_reserve_domains")
async def handle_show_reserve_domains_callback(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку 'Показать резервные домены'."""
    try:
        # Безопасное получение резервных доменов для этого чата
        success, sites_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_sites').select(
                'id, url, original_url, domain_expires_at, hosting_expires_at'
            ).eq('chat_id', callback.message.chat.id).eq('is_reserve_domain', True).execute()
        )
        
        if not success:
            logging.error(f"Не удалось получить резервные домены: {sites_result}")
            await callback.answer("Ошибка при получении резервных доменов.")
            return
        
        if not sites_result.data:
            await callback.answer("Резервных доменов не найдено.")
            return
        
        results = []
        for site in sites_result.data:
            display_url = site['original_url'] if site['original_url'] else site['url']
            site_info = f"**URL:** {display_url}\n**Статус:** 🔄 резервный домен (проверка пропущена)"
            
            # Добавляем информацию о сроках окончания домена
            if site.get('domain_expires_at'):
                domain_date = datetime.fromisoformat(site['domain_expires_at']).date()
                domain_days_left = (domain_date - datetime.now(timezone.utc).date()).days
                if domain_days_left <= 0:
                    domain_status = f"⚠️ **Домен истёк!** ({domain_date.strftime('%d.%m.%Y')})"
                elif domain_days_left <= 30:
                    domain_status = f"⚠️ Домен истекает через {domain_days_left} дней ({domain_date.strftime('%d.%m.%Y')})"
                else:
                    domain_status = f"✅ Домен до {domain_date.strftime('%d.%m.%Y')}"
                site_info += f"\n**Домен:** {domain_status}"
            else:
                site_info += "\n**Домен:** Дата не установлена"
            
            # Добавляем информацию о сроках окончания хостинга
            if site.get('hosting_expires_at'):
                hosting_date = datetime.fromisoformat(site['hosting_expires_at']).date()
                hosting_days_left = (hosting_date - datetime.now(timezone.utc).date()).days
                if hosting_days_left <= 0:
                    hosting_status = f"⚠️ **Хостинг истёк!** ({hosting_date.strftime('%d.%m.%Y')})"
                elif hosting_days_left <= 30:
                    hosting_status = f"⚠️ Хостинг истекает через {hosting_days_left} дней ({hosting_date.strftime('%d.%m.%Y')})"
                else:
                    hosting_status = f"✅ Хостинг до {hosting_date.strftime('%d.%m.%Y')}"
                site_info += f"\n**Хостинг:** {hosting_status}"
            else:
                site_info += "\n**Хостинг:** Дата не установлена"
            
            results.append(site_info)
        
        response = "🔄 **Резервные домены в этом чате:**\n\n" + "\n\n".join(results)
        
        # Разбиваем сообщение на части и отправляем
        message_parts = split_message(response)
        for i, part in enumerate(message_parts):
            if i == 0:
                await callback.message.reply(part, parse_mode="Markdown")
            else:
                await bot.send_message(callback.message.chat.id, part, parse_mode="Markdown")
        
        await callback.answer("Резервные домены показаны.")
        
    except Exception as e:
        logging.error(f"Error in handle_show_reserve_domains_callback: {e}")
        await callback.answer("Ошибка при получении резервных доменов.")


# Вспомогательная функция для безопасного выполнения операций с Supabase
async def safe_supabase_operation(operation_func, max_retries=3, retry_delay=5):
    """
    Безопасное выполнение операции с Supabase с повторными попытками
    
    Args:
        operation_func: Функция, выполняющая операцию с Supabase
        max_retries: Максимальное количество попыток
        retry_delay: Задержка между попытками в секундах
    
    Returns:
        tuple: (success, result_or_error)
    """
    for attempt in range(max_retries):
        try:
            result = operation_func()
            return True, result
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Ошибка Supabase (попытка {attempt + 1}/{max_retries}): {error_msg}")
            
            # Проверяем на специфические ошибки JSON
            if "JSON could not be generated" in error_msg or "code 556" in error_msg:
                logging.error(f"Обнаружена критическая ошибка JSON (код 556): {error_msg}")
                if attempt < max_retries - 1:
                    logging.info(f"Повторная попытка через {retry_delay} секунд...")
                    await asyncio.sleep(retry_delay)
                    continue
            
            # Другие ошибки
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                return False, e
    
    return False, Exception("Превышено максимальное количество попыток")

# Функция проверки доступности сайтов (каждые 5 минут)
async def scheduled_availability_check():
    while True:
        try:
            # Безопасное получение списка сайтов с повторными попытками
            success, sites_result = await safe_supabase_operation(
                lambda: supabase.table('botmonitor_sites').select(
                    'id, url, original_url, chat_id, is_up, has_ssl, ssl_expires_at, is_reserve_domain'
                ).execute()
            )
            
            if not success:
                logging.error(f"Не удалось получить список сайтов: {sites_result}")
                await send_admin_notification(f"Критическая ошибка при получении списка сайтов: {sites_result}")
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            
            sites = sites_result.data
            if not sites:
                logging.info("Список сайтов пуст, пропускаем проверку")
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            logging.info(f"Начинаю проверку {len(sites)} сайтов")
            
            for site in sites:
                try:
                    chat_id = site['chat_id']
                    display_url = site['original_url'] or site['url']
                    site_id, url, original_url = site['id'], site['url'], site['original_url']
                    was_up, had_ssl, old_ssl_expires_at = site['is_up'], site['has_ssl'], site['ssl_expires_at']
                    now = datetime.now(timezone.utc)

                    # 1. Проверяем доступность с несколькими попытками
                    status, status_code, attempts = await check_site_with_retries(url)
                    status_changed = status != bool(was_up)

                    # 2. Проверяем SSL (только для обновления данных, без уведомлений)
                    has_ssl, ssl_info, ssl_expires_at = False, None, old_ssl_expires_at
                    if status and url.startswith('https://'):
                        ssl_info = await check_ssl_certificate(url)
                        has_ssl = ssl_info.get('has_ssl', False)
                        if has_ssl:
                            ssl_expires_at = ssl_info.get('expiry_date')

                    # 3. Безопасное обновление статуса в БД
                    update_success, update_result = await safe_supabase_operation(
                        lambda: supabase.table('botmonitor_sites').update({
                            'is_up': status,
                            'has_ssl': has_ssl,
                            'ssl_expires_at': ssl_expires_at.isoformat() if ssl_expires_at and hasattr(ssl_expires_at, 'isoformat') else ssl_expires_at,
                            'last_check': now.isoformat()
                        }).eq('id', site_id).execute()
                    )
                    
                    if not update_success:
                        logging.error(f"Не удалось обновить статус сайта {site_id}: {update_result}")
                        await send_admin_notification(f"Ошибка обновления сайта {display_url}: {update_result}")
                        continue

                    # 4. Отправляем уведомления о доступности (только для нерезервных доменов)
                    if status_changed and not site.get('is_reserve_domain', False):
                        if status:
                            message = f"✅ Сайт снова доступен!\nURL: {display_url}\nКод ответа: {status_code}"
                        else:
                            # Добавляем информацию о количестве попыток при недоступности
                            message = f"❌ Сайт стал недоступен!\nURL: {display_url}\nКод ответа: {status_code}\nПроверок выполнено: {attempts}/{DOWN_CHECK_ATTEMPTS}"
                        
                        try:
                            await send_notification(chat_id, message)
                        except Exception as notify_error:
                            logging.error(f"Ошибка отправки уведомления для сайта {site_id}: {notify_error}")
                
                except Exception as site_error:
                    logging.error(f"Ошибка при обработке сайта {site.get('id', 'unknown')}: {site_error}")
                    # Продолжаем обработку других сайтов даже если один вызвал ошибку
                    continue
            
            logging.info(f"Завершена проверка {len(sites)} сайтов")
                    
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Критическая ошибка в scheduled_availability_check: {error_msg}")
            
            # Детальное логирование ошибки
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            
            await send_admin_notification(f"Критическая ошибка в availability check: {error_msg}")
        
        await asyncio.sleep(CHECK_INTERVAL)

# Функция проверки уведомлений о сроках истечения (один раз в день)
async def scheduled_notification_check():
    while True:
        try:
            # Проверяем уведомления один раз в день в 9:00 UTC
            now = datetime.now(timezone.utc)
            if now.hour == 9 and now.minute < 5:  # Проверяем в течение 5 минут
                logging.info("Начинаю проверку уведомлений о сроках истечения")
                
                # Безопасное получение списка сайтов с повторными попытками
                success, sites_result = await safe_supabase_operation(
                    lambda: supabase.table('botmonitor_sites').select(
                        'id, url, original_url, chat_id, has_ssl, ssl_expires_at, domain_expires_at, hosting_expires_at, ssl_last_notification_day, domain_last_notification_day, hosting_last_notification_day'
                    ).execute()
                )
                
                if not success:
                    logging.error(f"Не удалось получить список сайтов для проверки уведомлений: {sites_result}")
                    await send_admin_notification(f"Критическая ошибка при получении сайтов для уведомлений: {sites_result}")
                    await asyncio.sleep(300)
                    continue
                
                sites = sites_result.data
                if not sites:
                    logging.info("Список сайтов пуст, пропускаем проверку уведомлений")
                    await asyncio.sleep(300)
                    continue

                logging.info(f"Проверяю уведомления для {len(sites)} сайтов")
                
                for site in sites:
                    try:
                        chat_id = site['chat_id']
                        display_url = site['original_url'] or site['url']
                        site_id = site['id']
                        now_date = now.date()
                        
                        # Новая логика уведомлений - только в конкретные дни
                        notification_days = {30, 14, 7, 6, 5, 4, 3, 2, 1}

                        # Проверка SSL
                        if site.get('has_ssl') and site.get('ssl_expires_at'):
                            ssl_expiry_date = datetime.fromisoformat(site['ssl_expires_at']).date()
                            days_left = (ssl_expiry_date - now_date).days
                            
                            if days_left in notification_days or days_left <= 0:
                                last_ssl_notification = site.get('ssl_last_notification_day')
                                if last_ssl_notification != now_date or last_ssl_notification is None:
                                    if days_left <= 0:
                                        message = f"⚠️ SSL сертификат для {display_url} ИСТЁК!\nТребуется немедленное обновление."
                                    else:
                                        message = f"⚠️ SSL сертификат для {display_url} истекает через {days_left} дней!"
                                    
                                    await send_admin_notification(f"🔔 Уведомление для чата ID: {chat_id}\n\n{message}")
                                    
                                    # Безопасное обновление даты последнего SSL уведомления
                                    update_success, update_result = await safe_supabase_operation(
                                        lambda: supabase.table('botmonitor_sites').update({
                                            'ssl_last_notification_day': now_date.isoformat()
                                        }).eq('id', site_id).execute()
                                    )
                                    
                                    if not update_success:
                                        logging.error(f"Не удалось обновить дату SSL уведомления для сайта {site_id}: {update_result}")

                        # Проверка домена
                        if site.get('domain_expires_at'):
                            domain_expiry_date = datetime.fromisoformat(site['domain_expires_at']).date()
                            days_left = (domain_expiry_date - now_date).days
                            
                            if days_left in notification_days or days_left <= 0:
                                last_domain_notification = site.get('domain_last_notification_day')
                                if last_domain_notification != now_date or last_domain_notification is None:
                                    message = f"‼️ **Домен:** Срок оплаты для `{display_url}` истекает через **{days_left} дней** ({domain_expiry_date.strftime('%d.%m.%Y')})!"
                                    keyboard = get_renewal_keyboard(site_id, "domain")
                                    target_chat_id = ADMIN_CHAT_ID if ONLY_ADMIN_PUSH else chat_id
                                    
                                    try:
                                        await bot.send_message(target_chat_id, message, reply_markup=keyboard, parse_mode="Markdown")
                                    except Exception as send_error:
                                        logging.error(f"Ошибка отправки уведомления о домене для сайта {site_id}: {send_error}")
                                    
                                    # Безопасное обновление даты последнего уведомления о домене
                                    update_success, update_result = await safe_supabase_operation(
                                        lambda: supabase.table('botmonitor_sites').update({
                                            'domain_last_notification_day': now_date.isoformat()
                                        }).eq('id', site_id).execute()
                                    )
                                    
                                    if not update_success:
                                        logging.error(f"Не удалось обновить дату уведомления о домене для сайта {site_id}: {update_result}")

                        # Проверка хостинга
                        if site.get('hosting_expires_at'):
                            hosting_expiry_date = datetime.fromisoformat(site['hosting_expires_at']).date()
                            days_left = (hosting_expiry_date - now_date).days
                            
                            if days_left in notification_days or days_left <= 0:
                                last_hosting_notification = site.get('hosting_last_notification_day')
                                if last_hosting_notification != now_date or last_hosting_notification is None:
                                    message = f"🖥️ **Хостинг:** Срок оплаты для `{display_url}` истекает через **{days_left} дней** ({hosting_expiry_date.strftime('%d.%m.%Y')})!"
                                    keyboard = get_renewal_keyboard(site_id, "hosting")
                                    target_chat_id = ADMIN_CHAT_ID if ONLY_ADMIN_PUSH else chat_id
                                    
                                    try:
                                        await bot.send_message(target_chat_id, message, reply_markup=keyboard, parse_mode="Markdown")
                                    except Exception as send_error:
                                        logging.error(f"Ошибка отправки уведомления о хостинге для сайта {site_id}: {send_error}")
                                    
                                    # Безопасное обновление даты последнего уведомления о хостинге
                                    update_success, update_result = await safe_supabase_operation(
                                        lambda: supabase.table('botmonitor_sites').update({
                                            'hosting_last_notification_day': now_date.isoformat()
                                        }).eq('id', site_id).execute()
                                    )
                                    
                                    if not update_success:
                                        logging.error(f"Не удалось обновить дату уведомления о хостинге для сайта {site_id}: {update_result}")
                    
                    except Exception as site_error:
                        logging.error(f"Ошибка при обработке уведомлений для сайта {site.get('id', 'unknown')}: {site_error}")
                        # Продолжаем обработку других сайтов даже если один вызвал ошибку
                        continue
                
                logging.info(f"Завершена проверка уведомлений для {len(sites)} сайтов")

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Критическая ошибка в scheduled_notification_check: {error_msg}")
            
            # Детальное логирование ошибки
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            
            await send_admin_notification(f"Критическая ошибка в notification check: {error_msg}")
        
        # Проверяем уведомления каждые 5 минут, но отправляем только в 9:00
        await asyncio.sleep(300)  # 5 минут


# Запуск периодических проверок как фоновые задачи
async def on_startup():
    asyncio.create_task(scheduled_availability_check())
    asyncio.create_task(scheduled_notification_check())


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