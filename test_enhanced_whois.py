"""
Тестовый скрипт для проверки улучшенного WHOIS мониторинга
"""

import asyncio
import logging
import sys
import time
from datetime import datetime, timezone

# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Импортируем улучшенные модули
from whois_improvements import WHOISBatchProcessor, WHOISRetryManager, create_whois_monitoring_dashboard
from whois_watchdog import get_whois_expiry_date


async def test_retry_manager():
    """Тестирование менеджера повторных попыток"""
    print("\n🔄 Тестирование менеджера повторных попыток...")
    
    retry_manager = WHOISRetryManager(max_retries=3, base_delay=0.5)
    
    # Тестируем домены с разными проблемами
    test_domains = [
        'google.com',      # Надежный домен
        'example.com',     # Стандартный домен
        'цифровизируем.рф', # Кириллический домен (может быть проблема)
        'invalid-domain-that-does-not-exist-12345.com',  # Несуществующий домен
    ]
    
    for domain in test_domains:
        print(f"\n📋 Проверяем домен: {domain}")
        start_time = time.time()
        
        result = await retry_manager.get_whois_with_retry(domain, get_whois_expiry_date)
        
        duration = time.time() - start_time
        
        if result:
            print(f"✅ Успешно: {result.date()} (за {duration:.2f}с)")
        else:
            print(f"❌ Ошибка (за {duration:.2f}с)")
        
        # Показываем количество попыток
        retry_count = retry_manager.retry_count.get(domain.lower(), 0)
        print(f"📊 Попыток: {retry_count}")


async def test_batch_processor():
    """Тестирование пакетного процессора"""
    print("\n📦 Тестирование пакетного процессора...")
    
    processor = WHOISBatchProcessor(max_concurrent=3, delay_between_batches=0.5)
    
    # Тестируем различные домены
    test_domains = [
        'google.com',
        'github.com',
        'stackoverflow.com',
        'цифровизируем.рф',
        'example.org',
        'python.org',
        'openai.com',
        'microsoft.com',
        'invalid-domain-12345.com',
        'another-invalid-domain-67890.net'
    ]
    
    print(f"🔄 Обрабатываем {len(test_domains)} доменов пакетами...")
    start_time = time.time()
    
    results = await processor.process_domains_batch(test_domains, get_whois_expiry_date)
    
    duration = time.time() - start_time
    stats = results['stats']
    
    print(f"\n📊 Результаты пакетной обработки:")
    print(f"⏱️ Время: {duration:.2f}с")
    print(f"📈 Производительность: {stats['total']/duration:.1f} дом/с")
    print(f"✅ Успешно: {stats['successful']}")
    print(f"💾 Из кэша: {stats['cached']}")
    print(f"❌ Ошибки: {stats['failed']}")
    
    # Показываем успешные результаты
    if results['successful']:
        print(f"\n✅ Успешные домены:")
        for domain, expiry_date in list(results['successful'].items())[:5]:
            print(f"  • {domain}: {expiry_date.date()}")
    
    # Показываем ошибки
    if results['failed']:
        print(f"\n❌ Домены с ошибками:")
        for domain, error in list(results['failed'].items())[:3]:
            print(f"  • {domain}: {error}")


async def test_cache_performance():
    """Тестирование производительности кэша"""
    print("\n💾 Тестирование производительности кэша...")
    
    retry_manager = WHOISRetryManager()
    test_domain = 'google.com'
    
    # Первая проверка (без кэша)
    print(f"🔄 Первая проверка {test_domain} (без кэша)...")
    start_time = time.time()
    result1 = await retry_manager.get_whois_with_retry(test_domain, get_whois_expiry_date)
    first_duration = time.time() - start_time
    
    if result1:
        print(f"✅ Успешно за {first_duration:.2f}с")
    
    # Вторая проверка (с кэшем)
    print(f"🔄 Вторая проверка {test_domain} (с кэшем)...")
    start_time = time.time()
    result2 = await retry_manager.get_whois_with_retry(test_domain, get_whois_expiry_date)
    second_duration = time.time() - start_time
    
    if result2:
        print(f"✅ Успешно за {second_duration:.2f}с")
    
    # Сравниваем результаты
    if first_duration > 0 and second_duration > 0:
        speedup = first_duration / second_duration
        print(f"\n📈 Ускорение за счет кэша: {speedup:.1f}x")
        print(f"💾 Экономия времени: {(first_duration - second_duration):.2f}с")


async def test_dashboard_generation():
    """Тестирование генерации дашборда"""
    print("\n📊 Тестирование генерации дашборда...")
    
    dashboard_html = create_whois_monitoring_dashboard()
    
    # Сохраняем дашборд
    filename = f"test_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(dashboard_html)
    
    print(f"✅ Дашборд сохранен в файл: {filename}")
    print(f"📏 Размер файла: {len(dashboard_html)} символов")


async def test_russian_domains():
    """Тестирование кириллических доменов"""
    print("\n🇷🇺 Тестирование кириллических доменов...")
    
    russian_domains = [
        'цифровизируем.рф',
        'кремль.рф',
        'госуслуги.рф',
        'яндекс.рф',
        'москва.рф'
    ]
    
    retry_manager = WHOISRetryManager(max_retries=2, base_delay=0.5)
    
    for domain in russian_domains:
        print(f"\n📋 Проверяем кириллический домен: {domain}")
        start_time = time.time()
        
        result = await retry_manager.get_whois_with_retry(domain, get_whois_expiry_date)
        
        duration = time.time() - start_time
        
        if result:
            days_left = (result.date() - datetime.now(timezone.utc).date()).days
            print(f"✅ Успешно: {result.date()} ({days_left} дней) за {duration:.2f}с")
        else:
            print(f"❌ Ошибка за {duration:.2f}с")


async def test_error_handling():
    """Тестирование обработки ошибок"""
    print("\n⚠️ Тестирование обработки ошибок...")
    
    error_domains = [
        'invalid-domain-without-tld',
        'domain-that-does-not-exist-12345.com',
        'xn--invalid-punycode-12345',
        'subdomain.subdomain.subdomain.invalid-domain.com'
    ]
    
    retry_manager = WHOISRetryManager(max_retries=2, base_delay=0.3)
    
    for domain in error_domains:
        print(f"\n📋 Тестируем ошибочный домен: {domain}")
        start_time = time.time()
        
        result = await retry_manager.get_whois_with_retry(domain, get_whois_expiry_date)
        
        duration = time.time() - start_time
        
        if result:
            print(f"⚠️ Неожиданный успех: {result.date()} за {duration:.2f}с")
        else:
            print(f"✅ Корректная обработка ошибки за {duration:.2f}с")
        
        # Показываем количество попыток
        retry_count = retry_manager.retry_count.get(domain.lower(), 0)
        print(f"📊 Попыток: {retry_count}")


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования улучшенного WHOIS мониторинга...")
    print("=" * 60)
    
    try:
        # Тест 1: Менеджер повторных попыток
        await test_retry_manager()
        
        print("\n" + "=" * 60)
        
        # Тест 2: Пакетный процессор
        await test_batch_processor()
        
        print("\n" + "=" * 60)
        
        # Тест 3: Производительность кэша
        await test_cache_performance()
        
        print("\n" + "=" * 60)
        
        # Тест 4: Генерация дашборда
        await test_dashboard_generation()
        
        print("\n" + "=" * 60)
        
        # Тест 5: Кириллические домены
        await test_russian_domains()
        
        print("\n" + "=" * 60)
        
        # Тест 6: Обработка ошибок
        await test_error_handling()
        
        print("\n" + "=" * 60)
        print("✅ Все тесты завершены!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())