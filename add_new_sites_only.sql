-- SQL-скрипт для добавления только НОВЫХ сайтов (исключая уже существующие)
-- Выполните этот скрипт в Supabase SQL Editor ПОСЛЕ update_existing_sites.sql

-- Добавляем только те сайты, которых еще нет в базе
INSERT INTO botmonitor_sites (
    url, 
    original_url, 
    user_id, 
    chat_id, 
    chat_type, 
    is_up, 
    has_ssl, 
    domain_expires_at, 
    hosting_expires_at, 
    last_check, 
    created_at
) VALUES 
-- Домены с датой истечения домена 30.03.2026 (БЕЗ хостинга)
('https://прогрэсс.рф', 'прогрэсс.рф', 1298530968, -4974303698, 'group', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://прогрэс.рф', 'прогрэс.рф', 1298530968, -4974303698, 'group', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://про-гресс.рф', 'про-гресс.рф', 1298530968, -4974303698, 'group', true, true, '2026-03-30', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 13.05.2026 (БЕЗ хостинга)
('https://жкалькор.рф', 'жкалькор.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://жк-алькор.рф', 'жк-алькор.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://алькор82.рф', 'алькор82.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://jkalkor.ru', 'jkalkor.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-13', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 27.04.2026 (БЕЗ хостинга)
('https://progres82.ru', 'progres82.ru', 1298530968, -4974303698, 'group', true, true, '2026-04-27', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 03.05.2026 (БЕЗ хостинга)
('https://миндаль.рус', 'миндаль.рус', 1298530968, -4974303698, 'group', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://кварталминдаль.рф', 'кварталминдаль.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://жк-миндаль.рф', 'жк-миндаль.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://kvartal-mindal.ru', 'kvartal-mindal.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-03', NULL, NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://ccg-crimea.ru', 'ccg-crimea.ru', 1298530968, -4974303698, 'group', true, true, '2025-12-07', NULL, NOW(), NOW()),

-- Домены с датой истечения 28.05.2026 (БЕЗ хостинга)
('https://siesta-crimea.ru', 'siesta-crimea.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://бархат-евпатория.рф', 'бархат-евпатория.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://вега-крым.рф', 'вега-крым.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://вега-евпатория.рф', 'вега-евпатория.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://бархат-крым.рф', 'бархат-крым.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://barhat-crimea.ru', 'barhat-crimea.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://vega-crimea.ru', 'vega-crimea.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://vega-evpatoria.ru', 'vega-evpatoria.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://сиеста-крым.рф', 'сиеста-крым.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://сиеста-новыйсвет.рф', 'сиеста-новыйсвет.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://бархат-новыйсвет.рф', 'бархат-новыйсвет.рф', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://barhat-evpatoria.ru', 'barhat-evpatoria.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-28', NULL, NOW(), NOW()),

-- Домены с датой истечения 06.12.2025 (БЕЗ хостинга)
('https://кварталпредгорье.рф', 'кварталпредгорье.рф', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://жкпредгорье.рус', 'жкпредгорье.рус', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://predgorie-crimea.ru', 'predgorie-crimea.ru', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://квартал-предгорье.рф', 'квартал-предгорье.рф', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://жк-предгорье.рф', 'жк-предгорье.рф', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://предгорье.рус', 'предгорье.рус', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://predgorie82.ru', 'predgorie82.ru', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://predgorie.com', 'predgorie.com', 1298530968, -4974303698, 'group', true, true, '2025-12-06', NULL, NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://moinaco-resort.ru', 'moinaco-resort.ru', 1298530968, -4974303698, 'group', true, true, '2026-03-20', NULL, NOW(), NOW()),
('https://moinaco-riviera.ru', 'moinaco-riviera.ru', 1298530968, -4974303698, 'group', true, true, '2026-04-28', NULL, NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://modernatlas.ru', 'modernatlas.ru', 1298530968, -4974303698, 'group', true, true, '2025-09-20', NULL, NOW(), NOW()),
('https://atlassudak.com', 'atlassudak.com', 1298530968, -4974303698, 'group', true, true, '2026-06-13', NULL, NOW(), NOW()),

-- Домен с доменом и хостингом - atlas-apart.ru
('https://atlas-apart.ru', 'atlas-apart.ru', 1298530968, -4974303698, 'group', true, true, '2025-09-11', '2026-06-20', NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://startprospect82.ru', 'startprospect82.ru', 1298530968, -4974303698, 'group', true, true, '2026-05-12', NULL, NOW(), NOW()),
('https://startprospect82.online', 'startprospect82.online', 1298530968, -4974303698, 'group', true, true, '2026-05-12', NULL, NOW(), NOW()),
('https://prospect-82.online', 'prospect-82.online', 1298530968, -4974303698, 'group', true, true, '2025-09-20', NULL, NOW(), NOW()),
('https://prospect-82.ru', 'prospect-82.ru', 1298530968, -4974303698, 'group', true, true, '2025-09-20', NULL, NOW(), NOW()),
('https://проспект-82.рф', 'проспект-82.рф', 1298530968, -4974303698, 'group', true, true, '2026-08-22', NULL, NOW(), NOW()),

-- Домен с доменом и хостингом - prospect82.ru
('https://prospect82.ru', 'prospect82.ru', 1298530968, -4974303698, 'group', true, true, '2026-08-22', '2025-09-14', NOW(), NOW());

-- Проверяем результат
SELECT COUNT(*) as total_sites FROM botmonitor_sites WHERE chat_id = -4974303698;
