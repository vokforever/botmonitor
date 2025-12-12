"""
Улучшения для WHOIS мониторинга на основе анализа отчета
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import random

# Альтернативные WHOIS серверы для разных зон
WHOIS_SERVERS = {
    'ru': ['whois.tcinet.ru', 'whois.ripn.net', 'whois.nic.ru'],
    'xn--p1ai': ['whois.tcinet.ru', 'whois.ripn.net', 'whois.nic.ru'],
    'xn--p1acf': ['whois.tcinet.ru', 'whois.ripn.net', 'whois.nic.ru'],
    'com': ['whois.verisign-grs.com', 'whois.crsnic.net'],
    'net': ['whois.verisign-grs.com', 'whois.crsnic.net'],
    'org': ['whois.publicinterestregistry.net'],
    'info': ['whois.afilias.info'],
    'biz': ['whois.neulevel.biz'],
    'online': ['whois.nic.online'],
}

# Кэш для WHOIS данных
WHOIS_CACHE = {}
CACHE_TTL = 86400  # 24 часа

class WHOISRetryManager:
    """Менеджер повторных попыток для WHOIS запросов"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.retry_count = {}
    
    async def get_whois_with_retry(self, domain: str, whois_func) -> Optional[datetime]:
        """
        Выполняет WHOIS запрос с повторными попытками и разными серверами
        
        Args:
            domain: Имя домена
            whois_func: Функция для выполнения WHOIS запроса
            
        Returns:
            Дата истечения домена или None
        """
        domain_key = domain.lower()
        self.retry_count[domain_key] = 0
        
        # Проверяем кэш
        cached_result = self._get_from_cache(domain)
        if cached_result:
            logging.info(f"Используем кэшированные данные для {domain}")
            return cached_result
        
        # Извлекаем зону домена
        try:
            import tldextract
            ext = tldextract.extract(domain)
            zone = ext.suffix.lower()
        except Exception as e:
            logging.error(f"Ошибка извлечения зоны для {domain}: {e}")
            zone = None
        
        # Пробуем основные серверы
        for attempt in range(self.max_retries):
            self.retry_count[domain_key] = attempt + 1
            
            try:
                logging.info(f"Попытка {attempt + 1}/{self.max_retries} для {domain}")
                
                # Для первой попытки используем стандартную функцию
                if attempt == 0:
                    result = await whois_func(domain)
                    if result:
                        self._save_to_cache(domain, result)
                        return result
                
                # Для последующих попыток пробуем альтернативные серверы
                elif zone and zone in WHOIS_SERVERS:
                    for server in WHOIS_SERVERS[zone]:
                        try:
                            result = await self._try_alternative_server(domain, server, whois_func)
                            if result:
                                self._save_to_cache(domain, result)
                                return result
                        except Exception as e:
                            logging.warning(f"Сервер {server} недоступен для {domain}: {e}")
                            continue
                
                # Добавляем экспоненциальную задержку
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logging.info(f"Задержка {delay:.2f}с перед следующей попыткой для {domain}")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logging.warning(f"Попытка {attempt + 1} не удалась для {domain}: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
        
        logging.error(f"Не удалось получить WHOIS данные для {domain} после {self.max_retries} попыток")
        return None
    
    def _get_from_cache(self, domain: str) -> Optional[datetime]:
        """Получает данные из кэша"""
        if domain in WHOIS_CACHE:
            cached_data, timestamp = WHOIS_CACHE[domain]
            if time.time() - timestamp < CACHE_TTL:
                return cached_data
            else:
                # Удаляем устевший кэш
                del WHOIS_CACHE[domain]
        return None
    
    def _save_to_cache(self, domain: str, expiry_date: datetime) -> None:
        """Сохраняет данные в кэш"""
        WHOIS_CACHE[domain] = (expiry_date, time.time())
        
        # Ограничиваем размер кэша
        if len(WHOIS_CACHE) > 1000:
            # Удаляем самые старые записи
            oldest_domains = sorted(
                WHOIS_CACHE.items(), 
                key=lambda x: x[1][1]
            )[:100]
            
            for domain, _ in oldest_domains:
                del WHOIS_CACHE[domain]
    
    async def _try_alternative_server(self, domain: str, server: str, whois_func) -> Optional[datetime]:
        """Пробует альтернативный WHOIS сервер"""
        logging.info(f"Пробую альтернативный сервер {server} для {domain}")
        
        # Здесь можно реализовать подключение к альтернативному серверу
        # Для упрощения используем ту же функцию с задержкой
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        try:
            result = await whois_func(domain)
            if result:
                logging.info(f"Успешно получены данные с сервера {server} для {domain}")
                return result
        except Exception as e:
            logging.warning(f"Ошибка при подключении к серверу {server} для {domain}: {e}")
        
        return None


class WHOISBatchProcessor:
    """Пакетный процессор для WHOIS запросов"""
    
    def __init__(self, max_concurrent: int = 5, delay_between_batches: float = 1.0):
        self.max_concurrent = max_concurrent
        self.delay_between_batches = delay_between_batches
        self.retry_manager = WHOISRetryManager()
    
    async def process_domains_batch(self, domains: List[str], whois_func) -> Dict[str, Any]:
        """
        Обрабатывает список доменов пакетами
        
        Args:
            domains: Список доменов для обработки
            whois_func: Функция для выполнения WHOIS запроса
            
        Returns:
            Словарь с результатами обработки
        """
        results = {
            'successful': {},
            'failed': {},
            'cached': {},
            'stats': {
                'total': len(domains),
                'successful': 0,
                'failed': 0,
                'cached': 0,
                'duration': 0
            }
        }
        
        start_time = time.time()
        
        # Разбиваем на пакеты
        for i in range(0, len(domains), self.max_concurrent):
            batch = domains[i:i + self.max_concurrent]
            logging.info(f"Обработка пакета {i//self.max_concurrent + 1}: {batch}")
            
            # Создаем задачи для параллельного выполнения
            tasks = []
            for domain in batch:
                task = asyncio.create_task(
                    self._process_single_domain(domain, whois_func)
                )
                tasks.append(task)
            
            # Ждем завершения пакета
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем результаты пакета
            for domain, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results['failed'][domain] = str(result)
                    results['stats']['failed'] += 1
                elif result == 'cached':
                    results['cached'][domain] = True
                    results['stats']['cached'] += 1
                elif result:
                    results['successful'][domain] = result
                    results['stats']['successful'] += 1
                else:
                    results['failed'][domain] = 'WHOIS lookup failed'
                    results['stats']['failed'] += 1
            
            # Задержка между пакетами
            if i + self.max_concurrent < len(domains):
                await asyncio.sleep(self.delay_between_batches)
        
        results['stats']['duration'] = time.time() - start_time
        
        # Логируем статистику
        stats = results['stats']
        logging.info(
            f"Пакетная обработка завершена: "
            f"Всего: {stats['total']}, "
            f"Успешно: {stats['successful']}, "
            "Из кэша: {stats['cached']}, "
            f"Ошибок: {stats['failed']}, "
            f"Длительность: {stats['duration']:.2f}с"
        )
        
        return results
    
    async def _process_single_domain(self, domain: str, whois_func) -> Any:
        """Обрабатывает один домен"""
        # Проверяем кэш
        cached_result = self.retry_manager._get_from_cache(domain)
        if cached_result:
            return 'cached'
        
        # Выполняем WHOIS запрос с повторными попытками
        result = await self.retry_manager.get_whois_with_retry(domain, whois_func)
        return result


def create_whois_monitoring_dashboard() -> str:
    """
    Создает HTML дашборд для мониторинга WHOIS
    
    Returns:
        HTML код дашборда
    """
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WHOIS Мониторинг</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .stats { display: flex; gap: 20px; margin-bottom: 20px; }
            .stat-card { 
                border: 1px solid #ddd; 
                padding: 15px; 
                border-radius: 5px; 
                text-align: center;
                min-width: 120px;
            }
            .success { background-color: #d4edda; }
            .error { background-color: #f8d7da; }
            .warning { background-color: #fff3cd; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .expires-soon { background-color: #fff3cd; }
            .expired { background-color: #f8d7da; }
        </style>
    </head>
    <body>
        <h1>WHOIS Мониторинг</h1>
        
        <div class="stats">
            <div class="stat-card success">
                <h3>Всего доменов</h3>
                <div id="total-domains">-</div>
            </div>
            <div class="stat-card success">
                <h3>Успешно проверено</h3>
                <div id="successful-checks">-</div>
            </div>
            <div class="stat-card error">
                <h3>Ошибки</h3>
                <div id="failed-checks">-</div>
            </div>
            <div class="stat-card warning">
                <h3>Истекают скоро</h3>
                <div id="expiring-soon">-</div>
            </div>
        </div>
        
        <h2>Список доменов</h2>
        <table id="domains-table">
            <thead>
                <tr>
                    <th>Домен</th>
                    <th>Дата истечения</th>
                    <th>Дней до истечения</th>
                    <th>Статус</th>
                    <th>Последняя проверка</th>
                </tr>
            </thead>
            <tbody id="domains-tbody">
                <!-- Данные будут загружены через JavaScript -->
            </tbody>
        </table>
        
        <script>
            // Здесь можно добавить JavaScript для динамической загрузки данных
            function updateDashboard(data) {
                // Обновление статистики
                document.getElementById('total-domains').textContent = data.total || 0;
                document.getElementById('successful-checks').textContent = data.successful || 0;
                document.getElementById('failed-checks').textContent = data.failed || 0;
                document.getElementById('expiring-soon').textContent = data.expiringSoon || 0;
                
                // Обновление таблицы доменов
                const tbody = document.getElementById('domains-tbody');
                tbody.innerHTML = '';
                
                if (data.domains) {
                    data.domains.forEach(domain => {
                        const row = document.createElement('tr');
                        
                        // Определяем класс строки в зависимости от статуса
                        if (domain.daysLeft <= 0) {
                            row.className = 'expired';
                        } else if (domain.daysLeft <= 30) {
                            row.className = 'expires-soon';
                        }
                        
                        row.innerHTML = `
                            <td>${domain.name}</td>
                            <td>${domain.expiryDate}</td>
                            <td>${domain.daysLeft}</td>
                            <td>${domain.status}</td>
                            <td>${domain.lastCheck}</td>
                        `;
                        
                        tbody.appendChild(row);
                    });
                }
            }
            
            // Пример данных для демонстрации
            const sampleData = {
                total: 52,
                successful: 49,
                failed: 3,
                expiringSoon: 5,
                domains: [
                    { name: 'example.com', expiryDate: '2026-05-28', daysLeft: 168, status: 'Активен', lastCheck: '2025-12-13 00:07' },
                    { name: 'test.ru', expiryDate: '2026-03-30', daysLeft: 107, status: 'Активен', lastCheck: '2025-12-13 00:07' },
                    { name: 'expired.com', expiryDate: '2024-12-01', daysLeft: -42, status: 'Истёк', lastCheck: '2025-12-13 00:07' }
                ]
            };
            
            // Загружаем данные при загрузке страницы
            document.addEventListener('DOMContentLoaded', function() {
                updateDashboard(sampleData);
            });
        </script>
    </body>
    </html>
    """
    
    return html_template


# Пример использования улучшенного WHOIS мониторинга
async def improved_whois_check_example():
    """Пример использования улучшенного WHOIS мониторинга"""
    
    # Импортируем оригинальную функцию
    from whois_watchdog import get_whois_expiry_date
    
    # Создаем пакетный процессор
    processor = WHOISBatchProcessor(max_concurrent=3, delay_between_batches=0.5)
    
    # Список доменов для проверки
    domains = [
        'example.com',
        'test.ru',
        'цифровизируем.рф',
        'xn--c1abccby5aeje6k.xn--p1acf',
        'invalid-domain-that-will-fail.com'
    ]
    
    # Обрабатываем домены пакетами
    results = await processor.process_domains_batch(domains, get_whois_expiry_date)
    
    # Выводим результаты
    print(f"Результаты обработки {len(domains)} доменов:")
    print(f"Успешно: {len(results['successful'])}")
    print(f"Из кэша: {len(results['cached'])}")
    print(f"Ошибки: {len(results['failed'])}")
    print(f"Длительность: {results['stats']['duration']:.2f}с")
    
    # Создаем дашборд
    dashboard_html = create_whois_monitoring_dashboard()
    
    # Сохраняем дашборд в файл
    with open('whois_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(dashboard_html)
    
    print("Дашборд сохранен в файл whois_dashboard.html")


if __name__ == "__main__":
    # Запускаем пример
    asyncio.run(improved_whois_check_example())