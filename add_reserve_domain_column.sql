-- SQL-скрипт для добавления столбца "резервный домен" и обновления существующих записей
-- Выполните этот скрипт в Supabase SQL Editor

-- 1. Добавляем новый столбец is_reserve_domain (boolean, по умолчанию false)
ALTER TABLE botmonitor_sites 
ADD COLUMN is_reserve_domain BOOLEAN DEFAULT false;

-- 2. Обновляем существующие записи, помечая недоступные сайты как резервные
-- Сайты с кодом ответа 0 (недоступны)
UPDATE botmonitor_sites 
SET is_reserve_domain = true 
WHERE original_url IN (
    'прогрэсс.рф', 'прогрэс.рф', 'про-гресс.рф', 'жкпрогресс.рф',
    'жкалькор.рф', 'жк-алькор.рф', 'алькор82.рф', 'jkalkor.ru',
    'progres82.ru', 'миндаль.рус', 'кварталминдаль.рф', 'жк-миндаль.рф', 'kvartal-mindal.ru',
    'ccg-crimea.ru', 'siesta-crimea.ru', 'бархат-евпатория.рф', 'вега-крым.рф', 
    'вега-евпатория.рф', 'бархат-крым.рф', 'barhat-crimea.ru', 'vega-crimea.ru',
    'vega-evpatoria.ru', 'сиеста-крым.рф', 'сиеста-новыйсвет.рф', 'бархат-новыйсвет.рф',
    'barhat-evpatoria.ru', 'кварталпредгорье.рф', 'жкпредгорье.рус', 'predgorie-crimea.ru',
    'квартал-предгорье.рф', 'жк-предгорье.рф', 'предгорье.рус', 'predgorie82.ru', 'predgorie.com',
    'startprospect82.online', 'prospect-82.online', 'проспект-82.рф'
);

-- Сайты с кодом ответа 402 (требует оплаты) - тоже помечаем как резервные
UPDATE botmonitor_sites 
SET is_reserve_domain = true 
WHERE original_url IN (
    'moinaco-resort.ru', 'moinaco-riviera.ru', 'atlas-apart.ru', 'startprospect82.ru'
);

-- Сайт с кодом ответа 403 (запрещен) - тоже помечаем как резервные
UPDATE botmonitor_sites 
SET is_reserve_domain = true 
WHERE original_url IN (
    'prospect-82.ru'
);

-- 3. Проверяем результат
SELECT 
    original_url,
    is_up,
    is_reserve_domain,
    last_check
FROM botmonitor_sites 
WHERE chat_id = -4974303698 
ORDER BY is_reserve_domain DESC, original_url;

-- 4. Показываем статистику
SELECT 
    is_reserve_domain,
    COUNT(*) as count
FROM botmonitor_sites 
WHERE chat_id = -4974303698
GROUP BY is_reserve_domain;
