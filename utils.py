"""
Общие утилитарные функции для бота мониторинга сайтов
"""

import logging
import asyncio
from datetime import datetime, timezone
from supabase import Client


async def safe_supabase_operation(operation_func, max_retries=3, retry_delay=5, operation_name="unknown"):
    """
    Безопасное выполнение операции с Supabase с повторными попытками
    
    Args:
        operation_func: Функция, выполняющая операцию с Supabase
        max_retries: Максимальное количество попыток
        retry_delay: Задержка между попытками в секундах
        operation_name: Название операции для логирования
    
    Returns:
        tuple: (success, result_or_error)
    """
    start_time = datetime.now(timezone.utc)
    
    for attempt in range(max_retries):
        try:
            # Выполняем операцию в отдельном потоке, чтобы не блокировать основной цикл
            result = await asyncio.to_thread(operation_func)
             
            # Логируем успешное выполнение
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logging.debug(f"Операция Supabase '{operation_name}' выполнена успешно за {duration:.3f} сек (попытка {attempt + 1})")
             
            return True, result
        except Exception as e:
            error_msg = str(e)
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
             
            # Определяем тип ошибки для лучшей диагностики
            error_type = type(e).__name__
            if "JSON could not be generated" in error_msg or "code 556" in error_msg:
                error_type = "JSON_ERROR"
                logging.error(f"[{error_type}] Операция '{operation_name}' (попытка {attempt + 1}/{max_retries}): {error_msg}")
            elif "timeout" in error_msg.lower():
                error_type = "TIMEOUT"
                logging.warning(f"[{error_type}] Операция '{operation_name}' (попытка {attempt + 1}/{max_retries}): {error_msg}")
            elif "connection" in error_msg.lower():
                error_type = "CONNECTION"
                logging.warning(f"[{error_type}] Операция '{operation_name}' (попытка {attempt + 1}/{max_retries}): {error_msg}")
            else:
                logging.error(f"[{error_type}] Операция '{operation_name}' (попытка {attempt + 1}/{max_retries}): {error_msg}")
             
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
                total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logging.error(f"Операция '{operation_name}' не выполнена после {max_retries} попыток за {total_duration:.2f} сек")
                return False, e
     
    return False, Exception("Превышено максимальное количество попыток")


async def send_admin_notification(message: str, bot=None, admin_chat_id=None):
    """Отправляет уведомление администратору"""
    # Если бот или admin_chat_id не переданы, импортируем их локально
    if bot is None:
        from main import bot
    if admin_chat_id is None:
        from main import ADMIN_CHAT_ID
        admin_chat_id = ADMIN_CHAT_ID
    
    try:
        await bot.send_message(chat_id=admin_chat_id, text=message)
        logging.info(f"Уведомление отправлено админу: {message}")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления админу: {e}")