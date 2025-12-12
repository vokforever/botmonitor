#!/usr/bin/env python3
"""
Тестовый скрипт для проверки сценария с 403 Forbidden.
Проверяет, что сайт с 403 определяется как доступный через TCP.
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# Добавляем путь к основному файлу для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем функции из main.py
from main import check_site_availability, check_site_with_retries, tcp_check

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_403_scenario():
    """Тестируем сценарий с 403 Forbidden"""
    
    print("=== Тестирование сценария с 403 Forbidden ===")
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Тестируем сайт, который должен вернуть 403
    url = "https://httpbin.org/status/403"
    
    print(f"Проверка URL: {url}")
    print("-" * 50)
    
    try:
        # Тестируем основную функцию
        is_available, status_code, response_time, page_title, final_url, check_type = await check_site_availability(url)
        
        print(f"Результат: {'ДОСТУПЕН' if is_available else 'НЕДОСТУПЕН'}")
        print(f"Статус код: {status_code}")
        print(f"Время ответа: {response_time:.2f}с")
        print(f"Тип проверки: {check_type}")
        print(f"Финальный URL: {final_url}")
        
        if check_type == "tcp_only":
            print("\n✅ Успешно сработал TCP fallback для 403 Forbidden!")
            print("Сайт блокирует бота (403), но доступен через TCP-соединение.")
        elif check_type == "http" and not is_available:
            print("\n❌ Сайт определен как недоступный")
            if status_code == 403:
                print("Это может быть ложным срабатыванием - сайт блокирует бота, но жив.")
        
        # Дополнительно тестируем с повторными попытками
        print("\nПроверка с повторными попытками:")
        is_available_retry, status_code_retry, attempts, response_time_retry, page_title_retry, final_url_retry = await check_site_with_retries(url, max_attempts=2, retry_interval=2)
        
        print(f"Результат: {'ДОСТУПЕН' if is_available_retry else 'НЕДОСТУПЕН'}")
        print(f"Попыток: {attempts}")
        print(f"Статус код: {status_code_retry}")
        print(f"Время ответа: {response_time_retry:.2f}с")
        
    except Exception as e:
        print(f"Ошибка при проверке: {e}")

if __name__ == "__main__":
    asyncio.run(test_403_scenario())