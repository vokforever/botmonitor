import asyncio
import logging
import sys
import re
from datetime import datetime, timezone
from typing import Optional

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

async def get_whois_expiry_date(domain: str) -> Optional[datetime]:
    """
    Robust WHOIS lookup compatible with asyncwhois v1.1.12+
    Enhanced with Punycode (IDN) domain support for .ru/.рф domains
    """
    try:
        logging.info(f"Получение WHOIS данных для домена: {domain}")
        
        # 1. Clean Domain Extraction (removes http://, www., etc.)
        ext = tldextract.extract(domain)
        clean_domain = f"{ext.domain}.{ext.suffix}"
        
        # 1.1. Convert to Punycode if needed (for IDN domains)
        try:
            # Check if domain contains non-ASCII characters
            if any(ord(char) > 127 for char in clean_domain):
                import idna
                clean_domain = idna.encode(clean_domain).decode('ascii')
                logging.info(f"Преобразован в Punycode: {clean_domain}")
        except Exception as e:
            logging.warning(f"Не удалось преобразовать домен {clean_domain} в Punycode: {e}")
        
        if not ext.domain or not ext.suffix:
             logging.warning(f"Некорректный домен: {domain}")
             return None

        # 2. Async Lookup (FIXED API CALL)
        # Using the correct asyncwhois v1.1.12+ API
        result = await asyncwhois.aio_whois(clean_domain)
        
        # 3. Normalized Result Parsing
        whois_dict = {}
        
        # Case A: DomainLookup object with parser_output (Standard v1.1.12+)
        if hasattr(result, 'parser_output'):
            whois_dict = result.parser_output
        # Case B: Dictionary (Direct return)
        elif isinstance(result, dict):
            whois_dict = result
        # Case C: Tuple (Legacy/Specific calls)
        elif isinstance(result, tuple):
             # Try to find the dict in the tuple
             for item in result:
                 if isinstance(item, dict):
                     whois_dict = item
                     break

        if not whois_dict:
            logging.warning(f"Пустой результат WHOIS для {clean_domain}")
            return None

        # 4. Date Extraction (Enhanced)
        expiry_keys = [
            'expires', 'expiration_date', 'registry_expiry_date',
            'paid-till', 'paid_till', 'expiration', 'expire', # Common in RU/RF
            'free-date'
        ]
        expiry_date = None
        
        for key in expiry_keys:
            val = whois_dict.get(key)
            if val:
                expiry_date = val
                break
        
        # 5. NEW: Regex Fallback for .RF/.RU domains
        # Check both original suffix and punycode suffix
        domain_suffix = ext.suffix.lower()
        punycode_suffixes = ['ru', 'su', 'xn--p1ai', 'xn--p1acf']
        
        # Also check if the clean_domain has punycode suffix
        clean_ext = tldextract.extract(clean_domain)
        if clean_ext.suffix:
            punycode_suffix = clean_ext.suffix.lower()
            punycode_suffixes.append(punycode_suffix)
        
        # Check if either original suffix or punycode suffix is in our list
        should_apply_regex = (not expiry_date and
                           (domain_suffix in punycode_suffixes or
                            (clean_ext.suffix and clean_ext.suffix.lower() in punycode_suffixes)))
        
        if should_apply_regex:
            # Access raw text if available in the result object
            raw_text = ""
            
            # Case A: DomainLookup object with query_output
            if hasattr(result, 'query_output'):
                 raw_text = result.query_output
            # Case B: Tuple with raw text as first element (common in asyncwhois)
            elif isinstance(result, tuple) and len(result) > 0:
                 # First element is usually the raw WHOIS text
                 if isinstance(result[0], str):
                     raw_text = result[0]
                 # If first element is not text, check second element
                 elif len(result) > 1 and isinstance(result[1], str):
                     raw_text = result[1]
                 # If second element is a dict, try to find a text field
                 elif len(result) > 1 and isinstance(result[1], dict):
                     for key in ['raw', 'text', 'raw_text']:
                         if key in result[1] and isinstance(result[1][key], str):
                             raw_text = result[1][key]
                             break
            
            # Only apply regex if we have actual text content
            if raw_text and isinstance(raw_text, str):
                print(f"Применение regex к сыровому тексту для {clean_domain}")
                # Regex for "paid-till: 2025.10.15"
                match = re.search(r'paid-till:\s*(\d{4}[./-]\d{2}[./-]\d{2})', raw_text, re.IGNORECASE)
                if match:
                    expiry_date = match.group(1)
                    # Convert to standard format for parsing below
                    expiry_date = expiry_date.replace('.', '-')
                    print(f"Найдена дата через regex для {clean_domain}: {expiry_date}")
        
        # 6. Date Normalization
        if isinstance(expiry_date, list):
            expiry_date = expiry_date[0]
            
        if isinstance(expiry_date, str):
            # Try parsing common string formats if raw string returned
            try:
                # ISO format often works
                expiry_date = datetime.fromisoformat(expiry_date)
            except:
                # Try parsing YYYY-MM-DD format
                try:
                    expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d')
                except:
                    pass

        if isinstance(expiry_date, datetime):
            if expiry_date.tzinfo is None:
                expiry_date = expiry_date.replace(tzinfo=timezone.utc)
            return expiry_date
            
        logging.warning(f"Дата истечения не найдена или формат не распознан для {clean_domain}: {expiry_date}")
        return None

    except Exception as e:
        logging.error(f"WHOIS Critical Error for {domain}: {e}")
        return None

async def test_whois_fix():
    """Тестируем исправленную функцию WHOIS с поддержкой Punycode доменов"""
    test_domains = [
        "google.com",           # Стандартный домен .com
        "github.com",           # Стандартный домен .com
        "predgorie82.ru",       # Обычный домен .ru
        "яндекс.рф",            # Кириллический домен .рф
        "xn--d1acj3b.xn--p1ai", # Punycode версия яндекс.рф
        "пример.рф",            # Другой кириллический домен
        "xn--e1afmkfd.xn--p1ai", # Punycode версия пример.рф
        "цифровизируем.рф",     # Кириллический домен от пользователя
        "xn--b1agfcbb3akrf7aey.xn--p1ai" # Punycode версия цифровизируем.рф
    ]
    
    print("=== Тестирование WHOIS с поддержкой Punycode (IDN) доменов ===")
    
    for domain in test_domains:
        print(f"\n--- Проверка домена: {domain} ---")
        try:
            expiry_date = await get_whois_expiry_date(domain)
            if expiry_date:
                print(f"✅ Успешно получена дата истечения: {expiry_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                # Дополнительно проверяем, является ли домен Punycode
                ext = tldextract.extract(domain)
                if ext.suffix in ['xn--p1ai', 'xn--p1acf']:
                    print(f"   🌐 Это Punycode домен для .рф зоны")
            else:
                print(f"❌ Не удалось получить дату истечения")
        except Exception as e:
            print(f"❌ Ошибка при проверке домена: {e}")

if __name__ == "__main__":
    asyncio.run(test_whois_fix())