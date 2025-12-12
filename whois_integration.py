"""
Интеграция WHOIS Watchdog в основной бот мониторинга сайтов
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from supabase import Client
from whois_watchdog import (
    check_domains_routine, 
    schedule_daily_whois_check,
    handle_whois_confirm_callback,
    handle_whois_reject_callback,
    get_whois_expiry_date
)
from utils import safe_supabase_operation, send_admin_notification


# Состояния для добавления домена в мониторинг
class AddDomain(StatesGroup):
    waiting_for_domain = State()
    waiting_for_admin_chat = State()
    waiting_for_project_chat = State()
    waiting_for_expiry_date = State()
    waiting_for_reserve_status = State()


def register_whois_handlers(dp: Dispatcher, supabase: Client, bot: Bot):
    """
    Регистрирует обработчики для WHOIS Watchdog
    
    Args:
        dp: Dispatcher aiogram
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    
    # Обработчик команды /adddomain
    @dp.message(Command("adddomain"))
    async def cmd_adddomain(message: Message, state: FSMContext):
        """Начинает процесс добавления домена в WHOIS мониторинг"""
        await state.set_state(AddDomain.waiting_for_domain)
        await message.answer(
            "🕵️ **Добавление домена в WHOIS мониторинг**\n\n"
            "Отправьте имя домена, который хотите добавить в мониторинг.\n"
            "Например: example.com или цифровизируем.рф"
        )
    
    # Обработчик ввода домена
    @dp.message(AddDomain.waiting_for_domain)
    async def process_domain_input(message: Message, state: FSMContext):
        """Обрабатывает ввод домена"""
        domain_name = message.text.strip()
        
        # Сохраняем домен в состоянии
        await state.update_data(domain_name=domain_name)
        
        # Проверяем WHOIS для домена
        await message.answer(f"🔄 Проверяю WHOIS данные для домена {domain_name}...")
        
        try:
            expiry_date = await get_whois_expiry_date(domain_name)
            
            if not expiry_date:
                await message.answer(
                    f"❌ Не удалось получить WHOIS данные для домена {domain_name}.\n"
                    "Проверьте правильность написания домена и попробуйте снова."
                )
                await state.clear()
                return
            
            # Сохраняем дату истечения в состоянии
            await state.update_data(expiry_date=expiry_date.date())
            
            # Запрашиваем ID админского чата
            await state.set_state(AddDomain.waiting_for_admin_chat)
            await message.answer(
                f"✅ Получена дата истечения: {expiry_date.date().strftime('%d.%m.%Y')}\n\n"
                "Теперь отправьте ID чата для технических уведомлений (admin_chat_id):\n"
                "Используйте команду /myid чтобы узнать ваш Chat ID"
            )
            
        except Exception as e:
            logging.error(f"Ошибка при проверке WHOIS для домена {domain_name}: {e}")
            await message.answer(
                f"❌ Ошибка при проверке WHOIS для домена {domain_name}: {e}\n"
                "Попробуйте позже."
            )
            await state.clear()
    
    # Обработчик ввода admin_chat_id
    @dp.message(AddDomain.waiting_for_admin_chat)
    async def process_admin_chat_input(message: Message, state: FSMContext):
        """Обрабатывает ввод admin_chat_id"""
        try:
            admin_chat_id = int(message.text.strip())
            await state.update_data(admin_chat_id=admin_chat_id)
            
            # Запрашиваем ID проектного чата
            await state.set_state(AddDomain.waiting_for_project_chat)
            await message.answer(
                f"✅ Admin Chat ID: {admin_chat_id}\n\n"
                "Теперь отправьте ID чата для публичных уведомлений (project_chat_id):\n"
                "Это может быть тот же чат или другой"
            )
        except ValueError:
            await message.answer("❌ ID чата должен быть числом. Попробуйте снова.")
    
    # Обработчик ввода статуса резервного домена
    @dp.message(AddDomain.waiting_for_reserve_status)
    async def process_reserve_status_input(message: Message, state: FSMContext):
        """Обрабатывает ввод статуса резервного домена"""
        response = message.text.strip().lower()
        
        if response in ['да', 'д', 'yes', 'y']:
            is_reserve = True
            status_text = "резервный"
        elif response in ['нет', 'н', 'no', 'n']:
            is_reserve = False
            status_text = "обычный"
        else:
            await message.answer("❌ Неверный ответ. Отправьте 'да' или 'нет'")
            return
        
        # Получаем все данные из состояния
        data = await state.get_data()
        domain_name = data['domain_name']
        expiry_date = data['expiry_date']
        admin_chat_id = data['admin_chat_id']
        project_chat_id = data['project_chat_id']
        
        # Добавляем домен в БД
        await message.answer(f"💾 Добавляю {status_text} домен {domain_name} в базу данных...")
        
        success, result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').insert({
                'domain_name': domain_name,
                'current_expiry_date': expiry_date.isoformat(),
                'admin_chat_id': admin_chat_id,
                'project_chat_id': project_chat_id,
                'is_reserve_domain': is_reserve,
                'last_check_date': datetime.now(timezone.utc).isoformat()
            }).execute(),
            operation_name=f"insert_domain_{domain_name}"
        )
        
        if not success:
            await message.answer(f"❌ Ошибка при добавлении домена в БД: {result}")
            await state.clear()
            return
        
        reserve_info = "\n🔄 Это резервный домен (проверка доступности отключена)" if is_reserve else ""
        
        await message.answer(
            f"✅ **Домен успешно добавлен в WHOIS мониторинг!**\n\n"
            f"🌐 Домен: {domain_name}\n"
            f"📅 Истекает: {expiry_date.strftime('%d.%m.%Y')}\n"
            f"👨‍💻 Admin Chat ID: {admin_chat_id}\n"
            f"📢 Project Chat ID: {project_chat_id}\n"
            f"🔄 Статус: {status_text}{reserve_info}\n\n"
            f"Бот будет проверять домен ежедневно в 10:00 UTC и отправлять уведомления."
        )
        
        await state.clear()
    
    # Обработчик ввода project_chat_id
    @dp.message(AddDomain.waiting_for_project_chat)
    async def process_project_chat_input(message: Message, state: FSMContext):
        """Обрабатывает ввод project_chat_id"""
        try:
            project_chat_id = int(message.text.strip())
            await state.update_data(project_chat_id=project_chat_id)
            
            # Запрашиваем статус резервного домена
            await state.set_state(AddDomain.waiting_for_reserve_status)
            await message.answer(
                f"✅ Project Chat ID: {project_chat_id}\n\n"
                "Теперь укажите, является ли этот домен резервным:\n"
                "Отправьте 'да' если это резервный домен или 'нет' если обычный"
            )
            
        except ValueError:
            await message.answer("❌ ID чата должен быть числом. Попробуйте снова.")
    
    # Обработчики callback для кнопок подтверждения
    @dp.callback_query(F.data.startswith("whois_confirm:"))
    async def whois_confirm_handler(callback: CallbackQuery):
        """Обрабатывает подтверждение обновления домена"""
        await handle_whois_confirm_callback(callback, supabase, bot)
    
    @dp.callback_query(F.data.startswith("whois_reject:"))
    async def whois_reject_handler(callback: CallbackQuery):
        """Обрабатывает отклонение обновления домена"""
        await handle_whois_reject_callback(callback, supabase)
    
    # Обработчик команды /whoislist
    @dp.message(Command("whoislist"))
    async def cmd_whoislist(message: Message):
        """Показывает список доменов в WHOIS мониторинге"""
        success, domains_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').select('*').execute(),
            operation_name="get_whois_domains_list"
        )
        
        if not success:
            await message.answer("❌ Ошибка при получении списка доменов")
            return
        
        domains = domains_result.data
        if not domains:
            await message.answer("📝 Список доменов в WHOIS мониторинге пуст.\nИспользуйте /adddomain для добавления")
            return
        
        response = "🕵️ **Список доменов в WHOIS мониторинге:**\n\n"
        
        for domain in domains:
            domain_name = domain['domain_name']
            expiry_date = datetime.fromisoformat(domain['current_expiry_date']).date()
            admin_chat_id = domain['admin_chat_id']
            project_chat_id = domain['project_chat_id']
            is_reserve = domain.get('is_reserve_domain', False)
            last_check = domain['last_check_date']
            
            days_left = (expiry_date - datetime.now(timezone.utc).date()).days
            
            response += f"🌐 **{domain_name}**\n"
            response += f"📅 Истекает: {expiry_date.strftime('%d.%m.%Y')} ({days_left} дней)\n"
            response += f"👨‍💻 Admin Chat: {admin_chat_id}\n"
            response += f"📢 Project Chat: {project_chat_id}\n"
            response += f"🔄 Статус: {'резервный' if is_reserve else 'обычный'}\n"
            
            if last_check:
                last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                response += f"🔄 Последняя проверка: {last_check_dt.strftime('%d.%m.%Y %H:%M')}\n"
            
            response += "\n"
        
        await message.answer(response, parse_mode="Markdown")
    
    # Обработчик команды /checkwhois
    @dp.message(Command("checkwhois"))
    async def cmd_checkwhois(message: Message):
        """Проверяет WHOIS для указанного домена"""
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Использование: /checkwhois <имя_домена>\nПример: /checkwhois example.com")
            return
        
        domain_name = parts[1].strip()
        await message.answer(f"🔄 Проверяю WHOIS для домена {domain_name}...")
        
        try:
            expiry_date = await get_whois_expiry_date(domain_name)
            
            if not expiry_date:
                await message.answer(f"❌ Не удалось получить WHOIS данные для домена {domain_name}")
                return
            
            expiry_date_only = expiry_date.date()
            days_left = (expiry_date_only - datetime.now(timezone.utc).date()).days
            
            response = f"🕵️ **WHOIS информация для {domain_name}:**\n\n"
            response += f"📅 Дата истечения: {expiry_date_only.strftime('%d.%m.%Y')}\n"
            response += f"⏳ Осталось дней: {days_left}\n"
            
            if days_left <= 0:
                response += "⚠️ **Домен истёк!**"
            elif days_left <= 30:
                response += "⚠️ **Домен скоро истекает!**"
            else:
                response += "✅ Домен активен"
            
            await message.answer(response, parse_mode="Markdown")
            
        except Exception as e:
            logging.error(f"Ошибка при проверке WHOIS для домена {domain_name}: {e}")
            await message.answer(f"❌ Ошибка при проверке WHOIS: {e}")
    
    # Обработчик команды /whoisreserve
    @dp.message(Command("whoisreserve"))
    async def cmd_whoisreserve(message: Message):
        """Переключает статус резервного домена для WHOIS мониторинга"""
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Использование: /whoisreserve <имя_домена>\nПример: /whoisreserve example.com")
            return
        
        domain_name = parts[1].strip()
        
        # Ищем домен в БД
        success, domain_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').select('*').eq('domain_name', domain_name).execute(),
            operation_name=f"get_domain_for_reserve_{domain_name}"
        )
        
        if not success or not domain_result.data:
            await message.answer(f"❌ Домен {domain_name} не найден в WHOIS мониторинге")
            return
        
        domain = domain_result.data[0]
        current_status = domain.get('is_reserve_domain', False)
        new_status = not current_status
        
        # Обновляем статус
        update_success, update_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').update({
                'is_reserve_domain': new_status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('domain_name', domain_name).execute(),
            operation_name=f"update_reserve_status_{domain_name}"
        )
        
        if not update_success:
            await message.answer(f"❌ Ошибка при обновлении статуса домена: {update_result}")
            return
        
        status_text = "резервным" if new_status else "обычным"
        await message.answer(
            f"✅ Домен {domain_name} теперь является {status_text}.\n"
            f"Статус обновлен в базе данных."
        )


    # Обработчик команды /syncwhois
    @dp.message(Command("syncwhois"))
    async def cmd_syncwhois(message: Message):
        """Проверяет домены из основной таблицы и предлагает добавить отсутствующие в WHOIS мониторинг"""
        # Получаем сайты из основной таблицы
        success, sites_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_sites').select(
                'id, url, original_url, domain_expires_at, chat_id'
            ).execute(),
            operation_name="get_sites_for_sync"
        )
        
        if not success:
            await message.answer("❌ Ошибка при получении списка сайтов")
            return
        
        sites = sites_result.data
        if not sites:
            await message.answer("📝 Список сайтов пуст")
            return
        
        # Получаем уже добавленные домены из WHOIS мониторинга
        success, domains_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_domain_monitor').select('domain_name').execute(),
            operation_name="get_whois_domains_for_sync"
        )
        
        if not success:
            await message.answer("❌ Ошибка при получении списка WHOIS доменов")
            return
        
        monitored_domains = {d['domain_name'] for d in domains_result.data} if domains_result.data else set()
        
        # Ищем сайты без даты истечения домена
        sites_without_domain_date = []
        sites_with_domain_date_not_monitored = []
        
        for site in sites:
            url = site['original_url'] or site['url']
            # Извлекаем домен из URL с использованием улучшенной функции
            from main import extract_domain_from_url
            domain = extract_domain_from_url(url)
            
            if not site.get('domain_expires_at'):
                sites_without_domain_date.append({
                    'site_id': site['id'],
                    'domain': domain,
                    'url': url,
                    'chat_id': site['chat_id']
                })
            elif domain not in monitored_domains:
                sites_with_domain_date_not_monitored.append({
                    'site_id': site['id'],
                    'domain': domain,
                    'url': url,
                    'chat_id': site['chat_id'],
                    'expiry_date': site['domain_expires_at']
                })
        
        if not sites_without_domain_date and not sites_with_domain_date_not_monitored:
            await message.answer("✅ Все сайты уже добавлены в WHOIS мониторинг или имеют дату истечения домена")
            return
        
        response = "🔄 **Синхронизация WHOIS мониторинга**\n\n"
        
        if sites_without_domain_date:
            response += f"📝 **Сайты без даты истечения домена ({len(sites_without_domain_date)}):**\n"
            for site in sites_without_domain_date[:5]:  # Показываем первые 5
                response += f"• {site['domain']} (ID: {site['site_id']})\n"
            if len(sites_without_domain_date) > 5:
                response += f"... и еще {len(sites_without_domain_date) - 5}\n"
            response += "\n"
        
        if sites_with_domain_date_not_monitored:
            response += f"📅 **Сайты с датой истечения, но не в WHOIS мониторинге ({len(sites_with_domain_date_not_monitored)}):**\n"
            for site in sites_with_domain_date_not_monitored[:5]:  # Показываем первые 5
                response += f"• {site['domain']} (ID: {site['site_id']})\n"
            if len(sites_with_domain_date_not_monitored) > 5:
                response += f"... и еще {len(sites_with_domain_date_not_monitored) - 5}\n"
        
        response += "\nИспользуйте /adddomain для добавления доменов в WHOIS мониторинг"
        
        await message.answer(response, parse_mode="Markdown")
    
    # Обработчик команды /autowhois
    @dp.message(Command("autowhois"))
    async def cmd_autowhois(message: Message):
        """Запускает проверку WHOIS для всех доменов из botmonitor_sites"""
        # Получаем все сайты из основной таблицы
        success, sites_result = await safe_supabase_operation(
            lambda: supabase.table('botmonitor_sites').select(
                'id, url, original_url, chat_id, domain_expires_at'
            ).execute(),
            operation_name="get_all_sites_for_whois"
        )
        
        if not success:
            await message.answer("❌ Ошибка при получении списка сайтов")
            return
        
        sites = sites_result.data
        if not sites:
            await message.answer("📝 Список сайтов пуст")
            return
        
        await message.answer(f"🔄 Запускаю проверку WHOIS для {len(sites)} доменов...")
        
        updated_count = 0
        added_count = 0
        failed_count = 0
        
        for site in sites:
            url = site['original_url'] or site['url']
            # Извлекаем домен из URL с использованием улучшенной функции
            from main import extract_domain_from_url
            domain = extract_domain_from_url(url)
            
            try:
                # Получаем дату истечения через WHOIS
                expiry_date = await get_whois_expiry_date(domain)
                
                if not expiry_date:
                    logging.warning(f"Не удалось получить WHOIS для домена {domain}")
                    failed_count += 1
                    continue
                
                expiry_date_str = expiry_date.date().isoformat()
                
                # Проверяем, есть ли уже дата истечения в основной таблице
                if site.get('domain_expires_at'):
                    # Обновляем существующую дату в основной таблице
                    update_success, update_result = await safe_supabase_operation(
                        lambda: supabase.table('botmonitor_sites').update({
                            'domain_expires_at': expiry_date_str
                        }).eq('id', site['id']).execute(),
                        operation_name=f"update_domain_expiry_{site['id']}"
                    )
                    
                    if update_success:
                        updated_count += 1
                        logging.info(f"Обновлена дата домена {domain} в botmonitor_sites")
                    else:
                        failed_count += 1
                        logging.error(f"Ошибка обновления даты домена {domain}: {update_result}")
                else:
                    # Добавляем дату в основную таблицу, если ее нет
                    update_success, update_result = await safe_supabase_operation(
                        lambda: supabase.table('botmonitor_sites').update({
                            'domain_expires_at': expiry_date_str
                        }).eq('id', site['id']).execute(),
                        operation_name=f"add_domain_expiry_{site['id']}"
                    )
                    
                    if update_success:
                        updated_count += 1
                        logging.info(f"Добавлена дата домена {domain} в botmonitor_sites")
                    else:
                        failed_count += 1
                        logging.error(f"Ошибка добавления даты домена {domain}: {update_result}")
                
                # Проверяем, есть ли домен в WHOIS мониторинге
                domain_exists_result = await safe_supabase_operation(
                    lambda: supabase.table('botmonitor_domain_monitor').select('id').eq('domain_name', domain).execute(),
                    operation_name=f"check_domain_exists_{domain}"
                )
                
                if domain_exists_result[0] and not domain_exists_result[1].data:
                    # Добавляем в WHOIS мониторинг, если там еще нет
                    whois_success, whois_result = await safe_supabase_operation(
                        lambda: supabase.table('botmonitor_domain_monitor').insert({
                            'domain_name': domain,
                            'current_expiry_date': expiry_date_str,
                            'admin_chat_id': site['chat_id'],  # Используем тот же чат
                            'project_chat_id': site['chat_id'],  # Используем тот же чат
                            'is_reserve_domain': site.get('is_reserve_domain', False),  # Используем статус из основной таблицы
                            'last_check_date': datetime.now(timezone.utc).isoformat()
                        }).execute(),
                        operation_name=f"auto_insert_domain_{domain}"
                    )
                    
                    if whois_success:
                        added_count += 1
                        logging.info(f"Добавлен домен {domain} в WHOIS мониторинг")
                    else:
                        failed_count += 1
                        logging.error(f"Ошибка добавления домена {domain} в WHOIS мониторинг: {whois_result}")
                elif domain_exists_result[0] and domain_exists_result[1].data:
                    # Обновляем дату в WHOIS мониторинге, если домен уже там
                    whois_success, whois_result = await safe_supabase_operation(
                        lambda: supabase.table('botmonitor_domain_monitor').update({
                            'current_expiry_date': expiry_date_str,
                            'last_check_date': datetime.now(timezone.utc).isoformat()
                        }).eq('domain_name', domain).execute(),
                        operation_name=f"update_domain_expiry_whois_{domain}"
                    )
                    
                    if whois_success:
                        logging.info(f"Обновлена дата домена {domain} в WHOIS мониторинге")
                    else:
                        failed_count += 1
                        logging.error(f"Ошибка обновления даты домена {domain} в WHOIS мониторинге: {whois_result}")
                    
            except Exception as e:
                failed_count += 1
                logging.error(f"Ошибка при обработке домена {domain}: {e}")
        
        response = f"🔄 **Результаты проверки WHOIS для {len(sites)} доменов:**\n\n"
        response += f"📅 Обновлено дат в основной таблице: {updated_count}\n"
        response += f"➕ Добавлено в WHOIS мониторинг: {added_count}\n"
        response += f"❌ Ошибок: {failed_count}\n"
        
        if updated_count > 0 or added_count > 0:
            response += "\nИспользуйте /whoislist для просмотра доменов в WHOIS мониторинге"
        
        await message.answer(response, parse_mode="Markdown")


async def start_whois_watchdog(supabase: Client, bot: Bot):
    """
    Запускает WHOIS Watchdog как фоновую задачу
    
    Args:
        supabase: Клиент Supabase
        bot: Экземпляр бота aiogram
    """
    logging.info("Запуск WHOIS Watchdog...")
    
    # Запускаем планировщик ежедневных проверок
    asyncio.create_task(schedule_daily_whois_check(supabase, bot))
    
    # Отправляем уведомление о запуске
    await send_admin_notification("🕵️ WHOIS Watchdog запущен и готов к работе!")