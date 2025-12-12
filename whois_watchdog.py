import asyncio
import logging
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any

# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncwhois
import tldextract
from aiogram import Bot, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from supabase import Client

from utils import safe_supabase_operation, send_admin_notification

# Константы для WHOIS Watchdog
WHOIS_CHECK_HOUR = 10  # Время ежедневной проверки (10:00 UTC)
RENEWAL_THRESHOLD_DAYS = 30  # Порог для обнаружения продления
EXPIRATION_REMINDERS = [30, 7, 3, 1]  # Дни для напоминаний об истечении


async def get_whois_expiry_date(domain: str) -> Optional[datetime]:
    """
    Robust WHOIS lookup compatible with asyncwhois v1.1.12+
    """
    try:
        logging.info(f"Получение WHOIS данных для домена: {domain}")
        
        # 1. Clean Domain Extraction (removes http://, www., etc.)
        ext = tldextract.extract(domain)
        clean_domain = f"{ext.domain}.{ext.suffix}"
        
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

        # 4. Date Extraction (Try multiple common keys)
        expiry_keys = ['expires', 'expiration_date', 'registry_expiry_date', 'paid-till', 'free-date']
        expiry_date = None
        
        for key in expiry_keys:
            val = whois_dict.get(key)
            if val:
                expiry_date = val
                break
        
        # 5. Date Normalization
        if isinstance(expiry_date, list):
            expiry_date = expiry_date[0]
            
        if isinstance(expiry_date, str):
            # Try parsing common string formats if raw string returned
            try:
                # ISO format often works
                expiry_date = datetime.fromisoformat(expiry_date)
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


async def check_domains_routine(supabase: Client, bot: Bot) -> None:
    """
    Основная функция проверки доменов по расписанию
    
    Args:
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    try:
        logging.info("Запуск ежедневной проверки доменов WHOIS Watchdog")
        
        # Получаем все домены из таблицы botmonitor_domain_monitor
        success, domains_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').select('*').execute(),
            operation_name="get_domains_for_whois_check"
        )
        
        if not success:
            logging.error(f"Не удалось получить список доменов для проверки: {domains_result}")
            await send_admin_notification(f"🔥 WHOIS Watchdog: ошибка получения доменов: {domains_result}")
            return
            
        domains = domains_result.data
        if not domains:
            logging.info("Список доменов для WHOIS проверки пуст")
            return
            
        logging.info(f"Проверка {len(domains)} доменов")
        
        for domain_data in domains:
            try:
                await check_single_domain(domain_data, supabase, bot)
            except Exception as e:
                domain_name = domain_data.get('domain_name', 'unknown')
                logging.error(f"Ошибка при проверке домена {domain_name}: {e}")
                # Продолжаем проверку других доменов
                continue
                
        logging.info("Завершена ежедневная проверка доменов WHOIS Watchdog")
        
    except Exception as e:
        logging.error(f"Критическая ошибка в check_domains_routine: {e}")
        await send_admin_notification(f"🔥 WHOIS Watchdog: критическая ошибка: {e}")


async def check_single_domain(domain_data: Dict[str, Any], supabase: Client, bot: Bot) -> None:
    """
    Проверка отдельного домена
    
    Args:
        domain_data: Данные домена из БД
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    domain_id = domain_data['id']
    domain_name = domain_data['domain_name']
    current_expiry_date = datetime.fromisoformat(domain_data['current_expiry_date']).date()
    admin_chat_id = domain_data['admin_chat_id']
    project_chat_id = domain_data['project_chat_id']
    
    logging.debug(f"Проверка домена: {domain_name}")
    
    # Получаем данные WHOIS
    whois_expiry_date = await get_whois_expiry_date(domain_name)
    
    if not whois_expiry_date:
        logging.warning(f"Не удалось получить WHOIS данные для домена {domain_name}")
        return
        
    whois_expiry_date_only = whois_expiry_date.date()
    
    # Обновляем дату последней проверки
    await safe_supabase_operation(
        lambda: supabase.table('botmonitor_domain_monitor').update({
            'last_check_date': datetime.now(timezone.utc).isoformat()
        }).eq('id', domain_id).execute(),
        operation_name=f"update_domain_check_time_{domain_id}"
    )
    
    # Проверяем на продление (новая дата позже текущей более чем на 30 дней)
    days_difference = (whois_expiry_date_only - current_expiry_date).days
    
    if days_difference > RENEWAL_THRESHOLD_DAYS:
        logging.info(f"Обнаружено продление домена {domain_name}: с {current_expiry_date} до {whois_expiry_date_only}")
        
        # Отправляем уведомление администратору с кнопками подтверждения
        await send_renewal_confirmation(
            bot, domain_id, domain_name, 
            current_expiry_date, whois_expiry_date_only, 
            admin_chat_id
        )
    else:
        # Проверяем на приближение даты истечения
        await check_expiration_reminders(
            bot, domain_name, whois_expiry_date_only,
            admin_chat_id, project_chat_id
        )


async def send_renewal_confirmation(
    bot: Bot, domain_id: int, domain_name: str, 
    current_expiry: datetime.date, new_expiry: datetime.date, 
    admin_chat_id: int
) -> None:
    """
    Отправляет уведомление о продлении домена с кнопками подтверждения
    
    Args:
        bot: Экземпляр бота aiogram
        domain_id: ID домена в БД
        domain_name: Имя домена
        current_expiry: Текущая дата истечения
        new_expiry: Новая дата истечения
        admin_chat_id: ID чата администратора
    """
    # Создаем inline клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, обновить", 
                callback_data=f"whois_confirm:{domain_id}:{new_expiry.isoformat()}"
            ),
            InlineKeyboardButton(
                text="❌ Нет, ошибка парсера", 
                callback_data=f"whois_reject:{domain_id}"
            )
        ]
    ])
    
    message_text = (
        f"🕵️ **WHOIS Watchdog**\n\n"
        f"Обнаружено изменение даты для `{domain_name}`!\n\n"
        f"💾 Было: {current_expiry.strftime('%d.%m.%Y')}\n"
        f"🆕 Стало: {new_expiry.strftime('%d.%m.%Y')}\n\n"
        f"Подтверждаете обновление?"
    )
    
    try:
        await bot.send_message(
            chat_id=admin_chat_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        logging.info(f"Отправлено уведомление о продлении домена {domain_name} в чат {admin_chat_id}")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления о продлении домена {domain_name}: {e}")


async def check_expiration_reminders(
    bot: Bot, domain_name: str, expiry_date: datetime.date,
    admin_chat_id: int, project_chat_id: int
) -> None:
    """
    Проверяет и отправляет напоминания об истечении домена
    
    Args:
        bot: Экземпляр бота aiogram
        domain_name: Имя домена
        expiry_date: Дата истечения
        admin_chat_id: ID чата администратора
        project_chat_id: ID чата проекта
    """
    today = datetime.now(timezone.utc).date()
    days_left = (expiry_date - today).days
    
    # Проверяем, нужно ли отправить напоминание
    if days_left in EXPIRATION_REMINDERS or days_left <= 0:
        message_text = (
            f"⚠️ **Внимание: Истекает домен!**\n\n"
            f"🌐 Сайт: {domain_name}\n"
            f"📅 Дата окончания: {expiry_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Осталось дней: {days_left}\n\n"
            f"Срочно проверьте оплату у регистратора!"
        )
        
        # Отправляем в оба чата
        for chat_id in [admin_chat_id, project_chat_id]:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    parse_mode="Markdown"
                )
                logging.info(f"Отправлено напоминание об истечении домена {domain_name} в чат {chat_id}")
            except Exception as e:
                logging.error(f"Ошибка отправки напоминания об истечении домена {domain_name} в чат {chat_id}: {e}")


async def handle_whois_confirm_callback(
    callback: CallbackQuery, supabase: Client, bot: Bot
) -> None:
    """
    Обрабатывает нажатие на кнопку подтверждения обновления домена
    
    Args:
        callback: CallbackQuery от aiogram
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    try:
        # Разбираем callback_data
        _, domain_id_str, new_date_str = callback.data.split(":")
        domain_id = int(domain_id_str)
        new_expiry_date = datetime.fromisoformat(new_date_str).date()
        
        # Получаем данные домена
        success, domain_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').select('*').eq('id', domain_id).single().execute(),
            operation_name=f"get_domain_for_confirm_{domain_id}"
        )
        
        if not success or not domain_result.data:
            await callback.answer("Ошибка: домен не найден", show_alert=True)
            return
            
        domain_data = domain_result.data
        domain_name = domain_data['domain_name']
        project_chat_id = domain_data['project_chat_id']
        
        # Обновляем дату в БД
        update_success, update_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').update({
                'current_expiry_date': new_expiry_date.isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', domain_id).execute(),
            operation_name=f"update_domain_expiry_{domain_id}"
        )
        
        if not update_success:
            await callback.answer("Ошибка обновления даты в БД", show_alert=True)
            logging.error(f"Ошибка обновления даты домена {domain_id}: {update_result}")
            return
        
        # Обновляем сообщение администратора
        await callback.message.edit_text(
            f"✅ Данные для домена `{domain_name}` обновлены.",
            parse_mode="Markdown"
        )
        
        # Отправляем уведомление в проектный чат
        days_left = (new_expiry_date - datetime.now(timezone.utc).date()).days
        notification_text = (
            f"🎉 **Отличные новости!**\n\n"
            f"Домен {domain_name} успешно продлён.\n"
            f"📅 Оплачен до: {new_expiry_date.strftime('%d.%m.%Y')}\n"
            f"Следующее продление через {days_left} дней."
        )
        
        try:
            await bot.send_message(
                chat_id=project_chat_id,
                text=notification_text,
                parse_mode="Markdown"
            )
            logging.info(f"Отправлено уведомление о продлении домена {domain_name} в проектный чат {project_chat_id}")
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления о продлении в проектный чат: {e}")
        
        await callback.answer("Данные успешно обновлены", show_alert=True)
        
    except Exception as e:
        logging.error(f"Ошибка в handle_whois_confirm_callback: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


async def handle_whois_reject_callback(
    callback: CallbackQuery, supabase: Client
) -> None:
    """
    Обрабатывает нажатие на кнопку отклонения обновления домена
    
    Args:
        callback: CallbackQuery от aiogram
        supabase: Клиент Supabase
    """
    try:
        # Разбираем callback_data
        _, domain_id_str = callback.data.split(":")
        domain_id = int(domain_id_str)
        
        # Получаем данные домена
        success, domain_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').select('domain_name').eq('id', domain_id).single().execute(),
            operation_name=f"get_domain_for_reject_{domain_id}"
        )
        
        if not success or not domain_result.data:
            await callback.answer("Ошибка: домен не найден", show_alert=True)
            return
            
        domain_name = domain_result.data['domain_name']
        
        # Обновляем сообщение администратора
        await callback.message.edit_text(
            f"❌ Обновление даты для домена `{domain_name}` отклонено.\n"
            f"Будет использоваться предыдущая дата.",
            parse_mode="Markdown"
        )
        
        await callback.answer("Обновление отклонено", show_alert=True)
        
    except Exception as e:
        logging.error(f"Ошибка в handle_whois_reject_callback: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


async def schedule_daily_whois_check(supabase: Client, bot: Bot) -> None:
    """
    Планировщик ежедневной проверки WHOIS
    
    Args:
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    while True:
        try:
            # Получаем текущее время
            now = datetime.now(timezone.utc)
            
            # Проверяем, наступило ли время для проверки
            if now.hour == WHOIS_CHECK_HOUR and now.minute < 5:
                logging.info("Запуск плановой проверки WHOIS доменов")
                await check_domains_routine(supabase, bot)
                
                # Ждем до следующего дня
                await asyncio.sleep(3600)  # Ждем час, чтобы не запустить проверку повторно
                
            # Проверяем каждые 5 минут
            await asyncio.sleep(300)
            
        except Exception as e:
            logging.error(f"Ошибка в планировщике WHOIS: {e}")
            await asyncio.sleep(300)  # В случае ошибки ждем 5 минут и пробуем снова