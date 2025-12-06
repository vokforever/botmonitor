# Миграция базы данных для расширенного мониторинга

## Описание
Эта SQL миграция добавляет новые поля в таблицу `botmonitor_sites` для поддержки расширенных функций мониторинга.

## Новые функции
- ⏱️ Отслеживание времени ответа
- 🔢 Мониторинг HTTP кодов ответа
- 📝 Отслеживание заголовков страниц
- 🔄 Отслеживание переадресаций
- 📊 Статистика uptime

## SQL команды для выполнения

Выполните следующие команды в вашей Supabase консоли (SQL Editor):

```sql
-- Добавление полей для отслеживания времени ответа
ALTER TABLE botmonitor_sites 
ADD COLUMN IF NOT EXISTS response_time FLOAT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS avg_response_time FLOAT DEFAULT NULL;

-- Добавление поля для кода ответа HTTP
ALTER TABLE botmonitor_sites 
ADD COLUMN IF NOT EXISTS status_code INTEGER DEFAULT NULL;

-- Добавление полей для отслеживания заголовка и конечного URL
ALTER TABLE botmonitor_sites 
ADD COLUMN IF NOT EXISTS page_title TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS final_url TEXT DEFAULT NULL;

-- Добавление полей для статистики и отчетов
ALTER TABLE botmonitor_sites 
ADD COLUMN IF NOT EXISTS last_status_change TIMESTAMPTZ DEFAULT NULL,
ADD COLUMN IF NOT EXISTS total_checks INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS successful_checks INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS report_frequency TEXT DEFAULT NULL;

-- Комментарии для документации
COMMENT ON COLUMN botmonitor_sites.response_time IS 'Время ответа последней проверки (в секундах)';
COMMENT ON COLUMN botmonitor_sites.avg_response_time IS 'Среднее время ответа (в секундах)';
COMMENT ON COLUMN botmonitor_sites.status_code IS 'HTTP код ответа последней проверки';
COMMENT ON COLUMN botmonitor_sites.page_title IS 'Заголовок страницы (title) для отслеживания изменений';
COMMENT ON COLUMN botmonitor_sites.final_url IS 'Конечный URL после всех редиректов';
COMMENT ON COLUMN botmonitor_sites.last_status_change IS 'Время последнего изменения статуса (вверх/вниз)';
COMMENT ON COLUMN botmonitor_sites.total_checks IS 'Общее количество проверок';
COMMENT ON COLUMN botmonitor_sites.successful_checks IS 'Количество успешных проверок (для расчета uptime)';
COMMENT ON COLUMN botmonitor_sites.report_frequency IS 'Частота отправки отчетов: daily, weekly или NULL';
```

## Как выполнить миграцию

1. Откройте вашу Supabase консоль: https://app.supabase.com
2. Выберите ваш проект
3. Перейдите в раздел "SQL Editor"
4. Создайте новый запрос (New query)
5. Скопируйте и вставьте SQL команды выше
6. Нажмите "Run" для выполнения миграции

## Проверка

После выполнения миграции можно проверить, что все поля добавлены:

```sql
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'botmonitor_sites' 
ORDER BY ordinal_position;
```

## Примечание

Миграция безопасна и не повлияет на существующие данные. Все новые поля имеют значения по умолчанию (NULL или 0), поэтому старые записи будут работать корректно.
