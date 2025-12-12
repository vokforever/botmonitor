"""
Расширенная интеграция улучшенного WHOIS мониторинга в основной бот
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from supabase import Client
from whois_improvements import WHOISBatchProcessor, WHOISRetryManager, create_whois_monitoring_dashboard
from whois_watchdog import get_whois_expiry_date
from utils import safe_supabase_operation, send_admin_notification


class EnhancedWHOISManager:
    """Улучшенный менеджер WHOIS мониторинга"""
    
    def __init__(self, supabase: Client, bot: Bot):
        self.supabase = supabase
        self.bot = bot
        self.processor = WHOISBatchProcessor(max_concurrent=5, delay_between_batches=0.5)
        self.retry_manager = WHOISRetryManager(max_retries=3, base_delay=1.0)
        self.last_full_check = None
        self.check_interval = timedelta(hours=6)  # Полная проверка каждые 6 часов
    
    async def run_enhanced_autowhois(self, message: Message) -> None:
        """
        Запускает улучшенную проверку WHOIS для всех доменов
        
        Args:
            message: Сообщение от пользователя
        """
        await message.answer("🔄 Запускаю улучшенную проверку WHOIS для всех доменов...")
        
        # Получаем все сайты из основной таблицы
        success, sites_result = await safe_supabase_operation(
            lambda: self.supabase.table('botmonitor_sites').select(
                'id, url, original_url, chat_id, domain_expires_at'
            ).execute(),
            operation_name="get_all_sites_for_enhanced_whois"
        )
        
        if not success:
            await message.answer("❌ Ошибка при получении списка сайтов")
            return
        
        sites = sites_result.data
        if not sites:
            await message.answer("📝 Список сайтов пуст")
            return
        
        # Извлекаем домены
        domains = []
        site_domain_map = {}
        
        for site in sites:
            url = site['original_url'] or site['url']
            from main import extract_domain_from_url
            domain = extract_domain_from_url(url)
            
            domains.append(domain)
            site_domain_map[domain] = site
        
        # Обрабатываем домены пакетами
        status_msg = await message.answer(f"🔄 Обрабатываю {len(domains)} доменов улучшенным методом...")
        
        results = await self.processor.process_domains_batch(domains, get_whois_expiry_date)
        
        # Обрабатываем результаты
        updated_count = 0
        added_count = 0
        failed_count = 0
        cached_count = 0
        
        # Обновляем основную таблицу
        for domain, expiry_date in results['successful'].items():
            site = site_domain_map.get(domain)
            if not site:
                continue
            
            try:
                expiry_date_str = expiry_date.date().isoformat()
                
                # Обновляем дату в основной таблице
                update_success, update_result = await safe_supabase_operation(
                    lambda: self.supabase.table('botmonitor_sites').update({
                        'domain_expires_at': expiry_date_str
                    }).eq('id', site['id']).execute(),
                    operation_name=f"enhanced_update_domain_expiry_{site['id']}"
                )
                
                if update_success:
                    updated_count += 1
                    logging.info(f"Улучшенный метод: обновлена дата домена {domain}")
                else:
                    failed_count += 1
                    logging.error(f"Ошибка обновления даты домена {domain}: {update_result}")
                
                # Проверяем наличие в WHOIS мониторинге
                domain_exists_result = await safe_supabase_operation(
                    lambda: self.supabase.table('botmonitor_domain_monitor').select('id').eq('domain_name', domain).execute(),
                    operation_name=f"enhanced_check_domain_exists_{domain}"
                )
                
                if domain_exists_result[0] and not domain_exists_result[1].data:
                    # Добавляем в WHOIS мониторинг
                    whois_success, whois_result = await safe_supabase_operation(
                        lambda: self.supabase.table('botmonitor_domain_monitor').insert({
                            'domain_name': domain,
                            'current_expiry_date': expiry_date_str,
                            'admin_chat_id': site['chat_id'],
                            'project_chat_id': site['chat_id'],
                            'is_reserve_domain': site.get('is_reserve_domain', False),
                            'last_check_date': datetime.now(timezone.utc).isoformat()
                        }).execute(),
                        operation_name=f"enhanced_auto_insert_domain_{domain}"
                    )
                    
                    if whois_success:
                        added_count += 1
                        logging.info(f"Улучшенный метод: добавлен домен {domain} в WHOIS мониторинг")
                    else:
                        failed_count += 1
                        logging.error(f"Ошибка добавления домена {domain} в WHOIS мониторинг: {whois_result}")
                        
            except Exception as e:
                failed_count += 1
                logging.error(f"Ошибка при обработке домена {domain}: {e}")
        
        cached_count = len(results['cached'])
        failed_count += len(results['failed'])
        
        # Формируем отчет
        stats = results['stats']
        response = f"🚀 **Результаты улучшенной проверки WHOIS:**\n\n"
        response += f"📊 **Статистика обработки:**\n"
        response += f"• Всего доменов: {stats['total']}\n"
        response += f"• Успешно: {stats['successful']}\n"
        response += f"• Из кэша: {cached_count}\n"
        response += f"• Ошибок: {len(results['failed'])}\n"
        response += f"• Длительность: {stats['duration']:.2f}с\n"
        response += f"• Производительность: {stats['total']/stats['duration']:.1f} дом/с\n\n"
        
        response += f"📅 **Обновления в БД:**\n"
        response += f"• Обновлено дат: {updated_count}\n"
        response += f"• Добавлено в мониторинг: {added_count}\n"
        response += f"• Ошибок БД: {failed_count}\n\n"
        
        if results['failed']:
            response += f"❌ **Домены с ошибками:**\n"
            for domain, error in list(results['failed'].items())[:5]:  # Показываем первые 5
                response += f"• {domain}: {error}\n"
            if len(results['failed']) > 5:
                response += f"... и еще {len(results['failed']) - 5}\n"
            response += "\n"
        
        response += f"💾 **Кэш WHOIS:** {len(self.retry_manager._get_cache_size())} записей"
        
        await status_msg.edit_text(response, parse_mode="Markdown")
        
        # Обновляем время последней проверки
        self.last_full_check = datetime.now(timezone.utc)
    
    async def run_smart_check(self) -> None:
        """
        Запускает умную проверку только для доменов, которые нужно проверить
        """
        now = datetime.now(timezone.utc)
        
        # Проверяем, нужно ли запускать полную проверку
        if (self.last_full_check is None or 
            now - self.last_full_check > self.check_interval):
            logging.info("Запуск плановой улучшенной проверки WHOIS")
            await self.run_enhanced_autowhois()
            return
        
        # Иначе проверяем только домены с истекающими сроками
        await self.check_expiring_domains()
    
    async def check_expiring_domains(self) -> None:
        """
        Проверяет только домены с истекающими сроками (30 и менее дней)
        """
        thirty_days_from_now = (now + timedelta(days=30)).date().isoformat()
        
        # Получаем домены, которые истекают в ближайшие 30 дней
        success, domains_result = await safe_supabase_operation(
            lambda: self.supabase.table('botmonitor_sites').select(
                'id, url, original_url, chat_id, domain_expires_at'
            ).lte('domain_expires_at', thirty_days_from_now).execute(),
            operation_name="get_expiring_domains"
        )
        
        if not success or not domains_result.data:
            logging.info("Нет доменов с истекающими сроками")
            return
        
        domains = []
        site_domain_map = {}
        
        for site in domains_result.data:
            url = site['original_url'] or site['url']
            from main import extract_domain_from_url
            domain = extract_domain_from_url(url)
            
            domains.append(domain)
            site_domain_map[domain] = site
        
        logging.info(f"Проверка {len(domains)} доменов с истекающими сроками")
        
        # Обрабатываем домены
        results = await self.processor.process_domains_batch(domains, get_whois_expiry_date)
        
        # Отправляем уведомления о критических доменах
        await self.send_critical_notifications(results, site_domain_map)
    
    async def send_critical_notifications(self, results: Dict, site_domain_map: Dict) -> None:
        """
        Отправляет уведомления о критически важных доменах
        
        Args:
            results: Результаты проверки WHOIS
            site_domain_map: Соответствие доменов и сайтов
        """
        now = datetime.now(timezone.utc).date()
        
        for domain, expiry_date in results['successful'].items():
            if not expiry_date:
                continue
                
            days_left = (expiry_date.date() - now).days
            site = site_domain_map.get(domain)
            
            if not site:
                continue
            
            # Отправляем уведомления для доменов, которые истекают скоро
            if days_left <= 7:  # Критически важные
                message = f"🚨 **КРИТИЧЕСКИ ВАЖНО:**\n\n"
                message += f"Домен `{domain}` истекает через **{days_left} дней**!\n"
                message += f"Дата истечения: {expiry_date.date().strftime('%d.%m.%Y')}\n\n"
                message += f"Срочно требуется продление!"
                
                try:
                    await self.bot.send_message(
                        chat_id=site['chat_id'],
                        text=message,
                        parse_mode="Markdown"
                    )
                    logging.info(f"Отправлено критическое уведомление для домена {domain}")
                except Exception as e:
                    logging.error(f"Ошибка отправки уведомления для домена {domain}: {e}")
    
    def _get_cache_size(self) -> int:
        """Получает размер кэша"""
        return len(self.retry_manager._get_cache_size() if hasattr(self.retry_manager, '_get_cache_size') else [])


# Состояния для улучшенной WHOIS интеграции
class EnhancedWHOISStates(StatesGroup):
    waiting_for_dashboard_type = State()


def register_enhanced_whois_handlers(dp: Dispatcher, supabase: Client, bot: Bot):
    """
    Регистрирует обработчики для улучшенного WHOIS мониторинга
    
    Args:
        dp: Dispatcher aiogram
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    
    # Создаем менеджер
    enhanced_manager = EnhancedWHOISManager(supabase, bot)
    
    # Обработчик команды /enhancedwhois
    @dp.message(Command("enhancedwhois"))
    async def cmd_enhancedwhois(message: Message):
        """Запускает улучшенную проверку WHOIS"""
        await enhanced_manager.run_enhanced_autowhois(message)
    
    # Обработчик команды /whoisdashboard
    @dp.message(Command("whoisdashboard"))
    async def cmd_whoisdashboard(message: Message, state: FSMContext):
        """Создает и отправляет дашборд WHOIS мониторинга"""
        await state.set_state(EnhancedWHOISStates.waiting_for_dashboard_type)
        await message.answer(
            "📊 **Тип дашборда:**\n\n"
            "1. HTML дашборд (сохраняется в файл)\n"
            "2. Текстовый отчет в чате\n"
            "3. Статистика кэша\n\n"
            "Отправьте номер варианта:"
        )
    
    @dp.message(EnhancedWHOISStates.waiting_for_dashboard_type)
    async def process_dashboard_type(message: Message, state: FSMContext):
        """Обрабатывает выбор типа дашборда"""
        choice = message.text.strip()
        
        if choice == "1":
            # HTML дашборд
            await message.answer("🔄 Создаю HTML дашборд...")
            
            dashboard_html = create_whois_monitoring_dashboard()
            
            # Сохраняем в файл
            filename = f"whois_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(dashboard_html)
            
            await message.answer(f"✅ Дашборд сохранен в файл: {filename}")
            
        elif choice == "2":
            # Текстовый отчет
            await message.answer("🔄 Создаю текстовый отчет...")
            
            # Получаем статистику из БД
            success, domains_result = await safe_supabase_operation(
                lambda: supabase.table('botmonitor_domain_monitor').select('*').execute(),
                operation_name="get_whois_stats"
            )
            
            if not success:
                await message.answer("❌ Ошибка при получении статистики")
                await state.clear()
                return
            
            domains = domains_result.data if domains_result.data else []
            
            # Формируем отчет
            now = datetime.now(timezone.utc).date()
            expiring_soon = 0
            expired = 0
            
            for domain in domains:
                expiry_date = datetime.fromisoformat(domain['current_expiry_date']).date()
                days_left = (expiry_date - now).days
                
                if days_left <= 0:
                    expired += 1
                elif days_left <= 30:
                    expiring_soon += 1
            
            report = f"📊 **WHOIS Статистика:**\n\n"
            report += f"• Всего доменов в мониторинге: {len(domains)}\n"
            report += f"• Истекли: {expired}\n"
            report += f"• Истекают в течение 30 дней: {expiring_soon}\n"
            report += f"• Активных: {len(domains) - expired - expiring_soon}\n\n"
            
            report += f"💾 **Кэш:** {len(enhanced_manager.retry_manager._get_cache_size())} записей"
            
            await message.answer(report, parse_mode="Markdown")
            
        elif choice == "3":
            # Статистика кэша
            cache_size = len(enhanced_manager.retry_manager._get_cache_size())
            
            report = f"💾 **Статистика кэша WHOIS:**\n\n"
            report += f"• Записей в кэше: {cache_size}\n"
            report += f"• TTL кэша: 24 часа\n"
            report += f"• Макс. размер кэша: 1000 записей\n\n"
            
            if cache_size > 0:
                report += f"✅ Кэш работает и ускоряет проверки"
            else:
                report += f"ℹ️ Кэш пуст, будет заполняться при проверках"
            
            await message.answer(report, parse_mode="Markdown")
            
        else:
            await message.answer("❌ Неверный выбор. Отправьте число от 1 до 3")
            return
        
        await state.clear()
    
    # Обработчик команды /smartwhois
    @dp.message(Command("smartwhois"))
    async def cmd_smartwhois(message: Message):
        """Запускает умную проверку WHOIS"""
        await message.answer("🔄 Запускаю умную проверку WHOIS...")
        
        await enhanced_manager.run_smart_check()
        
        await message.answer("✅ Умная проверка WHOIS завершена")
    
    # Запускаем фоновую задачу для умных проверок
    async def start_smart_checks():
        """Запускает фоновую задачу умных проверок"""
        while True:
            try:
                await enhanced_manager.run_smart_check()
                # Проверяем каждый час
                await asyncio.sleep(3600)
            except Exception as e:
                logging.error(f"Ошибка в умной проверке WHOIS: {e}")
                await asyncio.sleep(300)  # 5 минут при ошибке
    
    # Запускаем фоновую задачу
    asyncio.create_task(start_smart_checks())
    
    logging.info("Улучшенный WHOIS мониторинг зарегистрирован и запущен")


# Функция для интеграции с основным ботом
async def integrate_enhanced_whois(dp: Dispatcher, supabase: Client, bot: Bot):
    """
    Интегрирует улучшенный WHOIS мониторинг в основной бот
    
    Args:
        dp: Dispatcher aiogram
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    register_enhanced_whois_handlers(dp, supabase, bot)
    
    # Отправляем уведомление о запуске
    await send_admin_notification("🚀 Улучшенный WHOIS мониторинг интегрирован и запущен!")
    
    logging.info("Улучшенный WHOIS мониторинг успешно интегрирован")