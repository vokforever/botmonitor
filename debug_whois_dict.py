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

async def debug_whois_dict(domain: str):
    """
    Детальный анализ словаря WHOIS для домена
    """
    try:
        logging.info(f"Анализ WHOIS словаря для домена: {domain}")
        
        # 1. Clean Domain Extraction
        ext = tldextract.extract(domain)
        clean_domain = f"{ext.domain}.{ext.suffix}"
        
        if not ext.domain or not ext.suffix:
             logging.warning(f"Некорректный домен: {domain}")
             return None

        # 2. Async Lookup
        result = await asyncwhois.aio_whois(clean_domain)
        
        print(f"\n=== АНАЛИЗ СЛОВАРЯ ДЛЯ {domain} ===")
        
        # Получаем словарь из результата
        whois_dict = {}
        if hasattr(result, 'parser_output'):
            whois_dict = result.parser_output
        elif isinstance(result, dict):
            whois_dict = result
        elif isinstance(result, tuple) and len(result) > 1:
            if isinstance(result[1], dict):
                whois_dict = result[1]
        
        # Анализируем ключи, связанные с датой
        date_keys = ['expires', 'expiration_date', 'registry_expiry_date', 'paid-till', 'paid_till', 'expiration', 'expire', 'free-date']
        
        print("Ключи, связанные с датой:")
        for key in date_keys:
            if key in whois_dict:
                print(f"  - {key}: {whois_dict[key]} (тип: {type(whois_dict[key])})")
        
        # Показываем все ключи для полноты картины
        print("\nВсе ключи в словаре:")
        for key in whois_dict.keys():
            value = whois_dict[key]
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"  - {key}: {value} (тип: {type(value)})")
        
        # Если есть сырой текст, анализируем его
        if isinstance(result, tuple) and len(result) > 0 and isinstance(result[0], str):
            raw_text = result[0]
            print("\nАнализ сырого текста на предмет дат:")
            
            # Ищем различные паттерны дат
            import re
            
            # Паттерн для paid-till
            paid_till_matches = re.findall(r'paid-till:\s*(\d{4}[./-]\d{2}[./-]\d{2})', raw_text, re.IGNORECASE)
            if paid_till_matches:
                print(f"  Найдены 'paid-till' даты: {paid_till_matches}")
            
            # Другие возможные паттерны
            date_patterns = [
                r'expires:\s*(\d{4}[./-]\d{2}[./-]\d{2})',
                r'expiration[-_]?date:\s*(\d{4}[./-]\d{2}[./-]\d{2})',
                r'paid[-_]?till:\s*(\d{4}[./-]\d{2}[./-]\d{2})',
                r'free[-_]?date:\s*(\d{4}[./-]\d{2}[./-]\d{2})',
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, raw_text, re.IGNORECASE)
                if matches:
                    print(f"  Паттерн '{pattern}': {matches}")
        
        return whois_dict

    except Exception as e:
        logging.error(f"Ошибка при анализе WHOIS для {domain}: {e}")
        return None

async def main():
    test_domains = [
        "predgorie82.ru",      # Работающий .ru домен
        "xn--d1acj3b.xn--p1ai" # Punycode версия
    ]
    
    for domain in test_domains:
        await debug_whois_dict(domain)
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())