import asyncio
import logging
import sys
from datetime import datetime, timezone

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncwhois
import tldextract

async def test_aio_whois_domain():
    """Тестируем функцию aio_whois_domain"""
    test_domain = "google.com"
    
    try:
        logging.info(f"Проверка домена: {test_domain}")
        
        # Используем правильную функцию API
        result = await asyncwhois.aio_whois_domain(test_domain)
        
        print(f"Тип результата: {type(result)}")
        print(f"Результат: {result}")
        
        # Проверяем структуру результата
        if hasattr(result, '__dict__'):
            print("\nАтрибуты результата:")
            for attr in dir(result):
                if not attr.startswith('_'):
                    value = getattr(result, attr)
                    print(f"  - {attr}: {type(value)} = {value}")
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_aio_whois_domain())