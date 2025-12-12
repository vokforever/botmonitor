import asyncio
import logging
import sys
import json
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

async def debug_whois_response(domain: str):
    """
    Детальный анализ ответа WHOIS для домена
    """
    try:
        logging.info(f"Анализ WHOIS ответа для домена: {domain}")
        
        # 1. Clean Domain Extraction
        ext = tldextract.extract(domain)
        clean_domain = f"{ext.domain}.{ext.suffix}"
        
        if not ext.domain or not ext.suffix:
             logging.warning(f"Некорректный домен: {domain}")
             return None

        # 2. Async Lookup
        result = await asyncwhois.aio_whois(clean_domain)
        
        print(f"\n=== АНАЛИЗ ОТВЕТА ДЛЯ {domain} ===")
        print(f"Тип результата: {type(result)}")
        
        # Анализируем структуру ответа
        if hasattr(result, 'parser_output'):
            print(f"Атрибут 'parser_output': {type(result.parser_output)}")
            if isinstance(result.parser_output, dict):
                print("Ключи в parser_output:")
                for key in result.parser_output.keys():
                    print(f"  - {key}: {result.parser_output[key]}")
        
        if hasattr(result, 'query_output'):
            print(f"Атрибут 'query_output': {type(result.query_output)}")
            if isinstance(result.query_output, str):
                print("Первые 500 символов query_output:")
                print(result.query_output[:500])
        
        if isinstance(result, dict):
            print("Результат - словарь. Ключи:")
            for key in result.keys():
                print(f"  - {key}: {result[key]}")
        
        if isinstance(result, tuple):
            print(f"Результат - кортеж из {len(result)} элементов:")
            for i, item in enumerate(result):
                print(f"  Элемент {i}: {type(item)}")
                if isinstance(item, dict):
                    print("    Ключи:")
                    for key in item.keys():
                        print(f"      - {key}")
                elif isinstance(item, str):
                    print(f"    Первые 200 символов:")
                    print(f"    {item[:200]}")
        
        return result

    except Exception as e:
        logging.error(f"Ошибка при анализе WHOIS для {domain}: {e}")
        return None

async def main():
    test_domains = [
        "predgorie82.ru",      # Работающий .ru домен
        "яндекс.рф",           # Кириллический домен .рф
        "xn--d1acj3b.xn--p1ai" # Punycode версия
    ]
    
    for domain in test_domains:
        await debug_whois_response(domain)
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())