-- SQL-скрипт для обновления существующих сайтов новой информацией
-- Выполните этот скрипт в Supabase SQL Editor

-- Обновляем существующие сайты с новой информацией о датах истечения домена/хостинга
-- и перемещаем их в группу -4974303698

-- 1. Обновляем vladograd.com (ID 21 -> 27)
UPDATE botmonitor_sites 
SET 
    chat_id = -4974303698,
    chat_type = 'group',
    domain_expires_at = NULL,
    hosting_expires_at = '2026-07-02'
WHERE id = 21;

-- 2. Обновляем жкпрогресс.рф (ID 25)
UPDATE botmonitor_sites 
SET 
    chat_id = -4974303698,
    chat_type = 'group',
    domain_expires_at = '2026-03-30',
    hosting_expires_at = NULL
WHERE id = 25;

-- 3. Обновляем квартал-миндаль.рф (ID 26)
UPDATE botmonitor_sites 
SET 
    chat_id = -4974303698,
    chat_type = 'group',
    domain_expires_at = '2026-05-03',
    hosting_expires_at = NULL
WHERE id = 26;

-- 4. Обновляем жкпредгорье.рф (ID 22)
UPDATE botmonitor_sites 
SET 
    chat_id = -4974303698,
    chat_type = 'group',
    domain_expires_at = '2025-12-06',
    hosting_expires_at = '2026-07-02'
WHERE id = 22;

-- 5. Обновляем жигулинароща.рф (ID 20)
UPDATE botmonitor_sites 
SET 
    chat_id = -4974303698,
    chat_type = 'group',
    domain_expires_at = '2026-06-03',
    hosting_expires_at = '2026-04-22'
WHERE id = 20;

-- 6. Обновляем moinaco.ru (ID 23)
UPDATE botmonitor_sites 
SET 
    chat_id = -4974303698,
    chat_type = 'group',
    domain_expires_at = '2026-01-13',
    hosting_expires_at = '2027-06-21'
WHERE id = 23;

-- 7. Обновляем atlas-sudak.ru (ID 24)
UPDATE botmonitor_sites 
SET 
    chat_id = -4974303698,
    chat_type = 'group',
    domain_expires_at = '2026-07-08',
    hosting_expires_at = NULL
WHERE id = 24;

-- Удаляем дубликаты (оставляем только обновленные записи)
DELETE FROM botmonitor_sites 
WHERE id IN (27, 28);

-- Проверяем результат
SELECT 
    id,
    original_url,
    chat_id,
    domain_expires_at,
    hosting_expires_at
FROM botmonitor_sites 
WHERE original_url IN (
    'vladograd.com', 
    'жкпрогресс.рф', 
    'квартал-миндаль.рф',
    'жкпредгорье.рф',
    'жигулинароща.рф',
    'moinaco.ru',
    'atlas-sudak.ru'
)
ORDER BY original_url;
