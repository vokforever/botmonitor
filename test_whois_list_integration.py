"""
Тестирование интеграции WHOIS с командой /list
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Импортируем необходимые функции
from main import cmd_list, extract_domain_from_url
from whois_watchdog import get_whois_expiry_date


class MockMessage:
    """Мок для объекта Message из aiogram"""
    def __init__(self, chat_id, text):
        self.chat = Mock()
        self.chat.id = chat_id
        self.text = text
        self.from_user = Mock()
        self.from_user.id = 12345
    
    async def answer(self, text, **kwargs):
        print(f"BOT ANSWER: {text}")
        return Mock()
    
    async def edit_text(self, text, **kwargs):
        print(f"BOT EDIT: {text}")
        return Mock()


class MockBot:
    """Мок для объекта Bot"""
    async def send_message(self, chat_id, text, **kwargs):
        print(f"BOT SEND: {text}")
        return Mock()
    
    async def edit_message_text(self, text, chat_id, message_id, **kwargs):
        print(f"BOT EDIT MSG: {text}")
        return Mock()


class MockBot:
    """Мок для объекта Bot"""
    async def send_message(self, chat_id, text, **kwargs):
        print(f"BOT SEND: {text}")
        return Mock()
    
    async def edit_message_text(self, text, chat_id, message_id, **kwargs):
        print(f"BOT EDIT: {text}")
        return Mock()


class MockSupabase:
    """Мок для объекта Supabase"""
    def __init__(self):
        self.data = [
            {
                'id': 1,
                'url': 'https://example.com',
                'original_url': 'example.com',
                'is_up': 1,
                'has_ssl': 1,
                'ssl_expires_at': '2025-06-01T00:00:00+00:00',
                'domain_expires_at': None,  # Будет обновлено через WHOIS
                'hosting_expires_at': None,
                'last_check': '2025-01-01T12:00:00+00:00',
                'is_reserve_domain': False,
                'chat_id': 12345
            },
            {
                'id': 2,
                'url': 'https://test-domain.ru',
                'original_url': 'test-domain.ru',
                'is_up': 1,
                'has_ssl': 1,
                'ssl_expires_at': '2025-07-01T00:00:00+00:00',
                'domain_expires_at': '2025-03-30',  # Уже есть дата
                'hosting_expires_at': None,
                'last_check': '2025-01-01T12:00:00+00:00',
                'is_reserve_domain': False,
                'chat_id': 12345
            }
        ]
    
    def table(self, table_name):
        return self
    
    def select(self, fields, **kwargs):
        return self
    
    def eq(self, field, value):
        return self
    
    def execute(self):
        result = Mock()
        result.data = self.data
        return result
    
    def update(self, data):
        result = Mock()
        result.data = self.data
        return result


async def mock_get_whois_expiry_date(domain):
    """Мок для функции get_whois_expiry_date"""
    if domain == 'example.com':
        return datetime(2026, 3, 30, tzinfo=timezone.utc)  # Новая дата
    elif domain == 'test-domain.ru':
        return datetime(2025, 3, 30, tzinfo=timezone.utc)  # Текущая дата
    else:
        return None


async def test_cmd_list_with_whois():
    """Тестирование команды /list с обновлением WHOIS"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ КОМАНДЫ /list С ОБНОВЛЕНИЕМ WHOIS")
    print("=" * 60)
    
    # Создаем моки
    mock_message = MockMessage(chat_id=12345, text="/list")
    mock_bot = MockBot()
    mock_supabase = MockSupabase()
    
    # Заменяем реальную функцию на мок
    import main
    original_supabase = main.supabase
    original_get_whois_expiry_date = main.get_whois_expiry_date
    
    main.supabase = mock_supabase
    main.get_whois_expiry_date = mock_get_whois_expiry_date
    
    # Заменяем реальную функцию на мок
    import main
    original_supabase = main.supabase
    original_get_whois_expiry_date = main.get_whois_expiry_date
    
    main.supabase = mock_supabase
    main.get_whois_expiry_date = mock_get_whois_expiry_date
    
    try:
        # Выполняем команду
        await cmd_list(mock_message)
        print("\n✅ Тест успешно завершен!")
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении теста: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Восстанавливаем оригинальные функции
        main.supabase = original_supabase
        main.get_whois_expiry_date = original_get_whois_expiry_date


async def test_extract_domain_from_url():
    """Тестирование функции извлечения домена"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ФУНКЦИИ extract_domain_from_url")
    print("=" * 60)
    
    test_cases = [
        ("https://example.com", "example.com"),
        ("http://test-domain.ru", "test-domain.ru"),
        ("example.com", "example.com"),
        ("https://цифровизируем.рф", "xn--b1agfcbb3akrf7aey.xn--p1ai"),
        ("https://subdomain.example.com/path", "subdomain.example.com"),
        ("", ""),
    ]
    
    for url, expected in test_cases:
        result = extract_domain_from_url(url)
        status = "✅" if result == expected else "❌"
        print(f"{status} {url} -> {result} (ожидается: {expected})")


async def main_test():
    """Главная функция тестирования"""
    print("НАЧАЛО ТЕСТИРОВАНИЯ ИНТЕГРАЦИИ WHOIS С КОМАНДОЙ /list")
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    await test_extract_domain_from_url()
    await test_cmd_list_with_whois()
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main_test())