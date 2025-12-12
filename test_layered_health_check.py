#!/usr/bin/env python3
"""
Тестовый скрипт для проверки "Layered Health Check" логики.
Имитирует различные сценарии проверки доступности сайтов.
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Добавляем путь к основному файлу для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем функции из main.py
from main import check_site_availability, check_site_with_retries, tcp_check

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_layered_health_check():
    """Тестируем логику "Layered Health Check" на различных сайтах"""
    
    # Тестовые сайты
    test_sites = [
        # Сайт, который должен быть доступен
        "https://httpbin.org/status/200",
        
        # Сайт, который возвращает 403 (должен сработать TCP fallback)
        "https://httpbin.org/status/403",
        
        # Сайт, который возвращает 404
        "https://httpbin.org/status/404",
        
        # Сайт с медленным ответом
        "https://httpbin.org/delay/5",
        
        # Несуществующий сайт (должен провалиться и по HTTP, и по TCP)
        "https://nonexistent-domain-12345.com",
        
        # Реальный сайт с кириллическим доменом
        "https://цифровизируем.рф",
    ]
    
    print("=== Тестирование Layered Health Check ===")
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    for i, url in enumerate(test_sites, 1):
        print(f"Тест {i}/{len(test_sites)}: {url}")
        print("-" * 50)
        
        try:
            # Тестируем основную функцию
            is_available, status_code, response_time, page_title, final_url, check_type = await check_site_availability(url)
            
            print(f"Результат: {'ДОСТУПЕН' if is_available else 'НЕДОСТУПЕН'}")
            print(f"Статус код: {status_code}")
            print(f"Время ответа: {response_time:.2f}с")
            print(f"Тип проверки: {check_type}")
            print(f"Финальный URL: {final_url}")
            
            if page_title:
                print(f"Заголовок: {page_title[:100]}...")
            
            # Дополнительно тестируем с повторными попытками
            print("\nПроверка с повторными попытками:")
            is_available_retry, status_code_retry, attempts, response_time_retry, page_title_retry, final_url_retry = await check_site_with_retries(url, max_attempts=2, retry_interval=2)
            
            print(f"Результат: {'ДОСТУПЕН' if is_available_retry else 'НЕДОСТУПЕН'}")
            print(f"Попыток: {attempts}")
            print(f"Статус код: {status_code_retry}")
            print(f"Время ответа: {response_time_retry:.2f}с")
            
        except Exception as e:
            print(f"Ошибка при проверке: {e}")
        
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_layered_health_check())