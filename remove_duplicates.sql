-- SQL-скрипт для удаления дубликатов из таблицы botmonitor_sites
-- Выполните этот скрипт в Supabase SQL Editor

-- Сначала посмотрим на дубликаты
SELECT 
    url, 
    original_url, 
    chat_id,
    COUNT(*) as count
FROM botmonitor_sites 
GROUP BY url, original_url, chat_id
HAVING COUNT(*) > 1
ORDER BY count DESC;

-- Удаляем дубликаты, оставляя только самую новую запись (по created_at)
WITH duplicates AS (
    SELECT 
        id,
        ROW_NUMBER() OVER (
            PARTITION BY url, original_url, chat_id 
            ORDER BY created_at DESC
        ) as rn
    FROM botmonitor_sites
)
DELETE FROM botmonitor_sites 
WHERE id IN (
    SELECT id 
    FROM duplicates 
    WHERE rn > 1
);

-- Проверяем результат
SELECT 
    url, 
    original_url, 
    chat_id,
    COUNT(*) as count
FROM botmonitor_sites 
GROUP BY url, original_url, chat_id
HAVING COUNT(*) > 1
ORDER BY count DESC;

-- Показываем общее количество записей
SELECT COUNT(*) as total_records FROM botmonitor_sites;
