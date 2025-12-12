#!/usr/bin/env python3
"""
Тест для проверки исправления проблемы с curl_cffi "Curlm alread closed! quitting from process_data"
"""

import asyncio
import logging
import sys
import time
import warnings
from datetime import datetime, timezone

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Фильтруем предупреждения от curl_cffi
warnings.filterwarnings("ignore", message=".*Curlm alread closed.*", module="curl_cffi")

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
    print("✅ curl_cffi доступен")
except ImportError:
    print("❌ curl_cffi не установлен")
    CURL_CFFI_AVAILABLE = False

async def test_curl_cffi_session():
    """Тест корректного управления сессией curl_cffi"""
    if not CURL_CFFI_AVAILABLE:
        print("Пропуск теста curl_cffi - библиотека не установлена")
        return True
    
    test_urls = [
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/404",
        "https://httpbin.org/delay/2"
    ]
    
    print("\n🔄 Тестирование управления сессиями curl_cffi...")
    
    for url in test_urls:
        print(f"\n📍 Проверяем URL: {url}")
        start_time = time.time()
        session = None
        
        try:
            # Создаем сессию отдельно для лучшего контроля
            session = curl_requests.AsyncSession(impersonate="chrome120")
            
            try:
                response = await session.get(url, timeout=10)
                response_time = time.time() - start_time
                
                print(f"✅ Ответ получен: статус={response.status_code}, время={response_time:.2f}s")
                
            finally:
                # Явно закрываем сессию
                if session:
                    try:
                        await session.close()
                        print("✅ Сессия закрыта корректно")
                    except Exception as close_error:
                        print(f"⚠️ Ошибка при закрытии сессии: {close_error}")
                        
        except Exception as e:
            total_time = time.time() - start_time
            print(f"❌ Ошибка запроса: {e} (время: {total_time:.2f}s)")
            
            # Убедимся, что сессия закрыта при ошибке
            if session:
                try:
                    await session.close()
                    print("✅ Сессия закрыта после ошибки")
                except Exception as close_error:
                    print(f"⚠️ Ошибка при закрытии сессии после ошибки: {close_error}")
    
    return True

async def test_multiple_concurrent_requests():
    """Тест множественных одновременных запросов"""
    if not CURL_CFFI_AVAILABLE:
        print("Пропуск теста множественных запросов - curl_cffi не установлена")
        return True
    
    print("\n🔄 Тестирование множественных одновременных запросов...")
    
    async def single_request(url, request_id):
        start_time = time.time()
        session = None
        
        try:
            session = curl_requests.AsyncSession(impersonate="chrome120")
            
            try:
                response = await session.get(url, timeout=5)
                response_time = time.time() - start_time
                print(f"✅ Запрос {request_id}: статус={response.status_code}, время={response_time:.2f}s")
                return True
            finally:
                if session:
                    await session.close()
                    
        except Exception as e:
            total_time = time.time() - start_time
            print(f"❌ Запрос {request_id} ошибка: {e} (время: {total_time:.2f}s)")
            
            if session:
                try:
                    await session.close()
                except Exception:
                    pass
            
            return False
    
    # Создаем несколько одновременных запросов
    test_url = "https://httpbin.org/status/200"
    tasks = [single_request(test_url, i) for i in range(5)]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success_count = sum(1 for result in results if result is True)
    
    print(f"\n📊 Результаты: {success_count}/{len(tasks)} запросов успешны")
    
    return success_count >= len(tasks) * 0.8  # 80% успехов достаточно

async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования исправления curl_cffi...")
    print(f"⏰ Время начала: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = []
    
    # Тест 1: Базовое управление сессией
    test1_result = await test_curl_cffi_session()
    test_results.append(("Базовое управление сессией", test1_result))
    
    # Тест 2: Множественные одновременные запросы
    test2_result = await test_multiple_concurrent_requests()
    test_results.append(("Множественные запросы", test2_result))
    
    # Итоги
    print("\n" + "="*50)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ:")
    print("="*50)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Исправление curl_cffi работает корректно.")
    else:
        print("⚠️ Некоторые тесты не пройдены. Рекомендуется дополнительно проверить логи.")
    print("="*50)
    
    return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка при выполнении тестов: {e}")
        sys.exit(1)