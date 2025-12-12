-- SQL-скрипт для массового добавления доменов с датами истечения домена и хостинга
-- Выполните этот скрипт в Supabase SQL Editor

-- Вставка доменов с датами истечения домена и хостинга
-- Замените NULL и 1298530968 на реальные значения

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
('https://прогрэсс.рф', 'прогрэсс.рф', 1298530968, -4974303698, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://прогрэс.рф', 'прогрэс.рф', 1298530968, -4974303698, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://про-гресс.рф', 'про-гресс.рф', 1298530968, -4974303698, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://жкпрогресс.рф', 'жкпрогресс.рф', 1298530968, -4974303698, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 13.05.2026 (БЕЗ хостинга)
('https://жкалькор.рф', 'жкалькор.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://жк-алькор.рф', 'жк-алькор.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://алькор82.рф', 'алькор82.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://jkalkor.ru', 'jkalkor.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 27.04.2026 (БЕЗ хостинга)
('https://progres82.ru', 'progres82.ru', 1298530968, -4974303698, 'private', true, true, '2026-04-27', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 03.05.2026 (БЕЗ хостинга)
('https://миндаль.рус', 'миндаль.рус', 1298530968, -4974303698, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://кварталминдаль.рф', 'кварталминдаль.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://квартал-миндаль.рф', 'квартал-миндаль.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://жк-миндаль.рф', 'жк-миндаль.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://kvartal-mindal.ru', 'kvartal-mindal.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),


-- Домены ТОЛЬКО с хостингом - 02.07.2026 (296 дней с 11.09.2025)
('https://vladograd.com', 'vladograd.com', 1298530968, -4974303698, 'private', true, true, NULL, '2026-07-02', NOW(), NOW()),

-- Домен с доменом и хостингом - жигулинароща.рф
('https://жигулинароща.рф', 'жигулинароща.рф', 1298530968, -4974303698, 'private', true, true, '2026-06-03', '2026-04-22', NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://ccg-crimea.ru', 'ccg-crimea.ru', 1298530968, -4974303698, 'private', true, true, '2025-12-07', NULL, NOW(), NOW()),

-- Домены с датой истечения 28.05.2026 (БЕЗ хостинга)
('https://siesta-crimea.ru', 'siesta-crimea.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://бархат-евпатория.рф', 'бархат-евпатория.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://вега-крым.рф', 'вега-крым.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://вега-евпатория.рф', 'вега-евпатория.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://бархат-крым.рф', 'бархат-крым.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://barhat-crimea.ru', 'barhat-crimea.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://vega-crimea.ru', 'vega-crimea.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://vega-evpatoria.ru', 'vega-evpatoria.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://сиеста-крым.рф', 'сиеста-крым.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://сиеста-новыйсвет.рф', 'сиеста-новыйсвет.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://бархат-новыйсвет.рф', 'бархат-новыйсвет.рф', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),
('https://barhat-evpatoria.ru', 'barhat-evpatoria.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-28', NULL, NOW(), NOW()),

-- Домены с датой истечения 06.12.2025 (БЕЗ хостинга)
('https://кварталпредгорье.рф', 'кварталпредгорье.рф', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://жкпредгорье.рус', 'жкпредгорье.рус', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://predgorie-crimea.ru', 'predgorie-crimea.ru', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://квартал-предгорье.рф', 'квартал-предгорье.рф', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://жк-предгорье.рф', 'жк-предгорье.рф', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://предгорье.рус', 'предгорье.рус', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://predgorie82.ru', 'predgorie82.ru', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),
('https://жкпредгорье.рф', 'жкпредгорье.рф', 1298530968, -4974303698, 'private', true, true, '2025-12-06', '2026-07-02', NOW(), NOW()),
('https://predgorie.com', 'predgorie.com', 1298530968, -4974303698, 'private', true, true, '2025-12-06', NULL, NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://moinaco-resort.ru', 'moinaco-resort.ru', 1298530968, -4974303698, 'private', true, true, '2026-03-20', NULL, NOW(), NOW()),
('https://moinaco-riviera.ru', 'moinaco-riviera.ru', 1298530968, -4974303698, 'private', true, true, '2026-04-28', NULL, NOW(), NOW()),

-- Домен с доменом и хостингом - moinaco.ru
('https://moinaco.ru', 'moinaco.ru', 1298530968, -4974303698, 'private', true, true, '2026-01-13', '2027-06-21', NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://modernatlas.ru', 'modernatlas.ru', 1298530968, -4974303698, 'private', true, true, '2025-09-20', NULL, NOW(), NOW()),
('https://atlas-sudak.ru', 'atlas-sudak.ru', 1298530968, -4974303698, 'private', true, true, '2026-07-08', NULL, NOW(), NOW()),
('https://atlassudak.com', 'atlassudak.com', 1298530968, -4974303698, 'private', true, true, '2026-06-13', NULL, NOW(), NOW()),

-- Домен с доменом и хостингом - atlas-apart.ru
('https://atlas-apart.ru', 'atlas-apart.ru', 1298530968, -4974303698, 'private', true, true, '2025-09-11', '2026-06-20', NOW(), NOW()),

-- Дополнительные домены с датами истечения
('https://startprospect82.ru', 'startprospect82.ru', 1298530968, -4974303698, 'private', true, true, '2026-05-12', NULL, NOW(), NOW()),
('https://startprospect82.online', 'startprospect82.online', 1298530968, -4974303698, 'private', true, true, '2026-05-12', NULL, NOW(), NOW()),
('https://prospect-82.online', 'prospect-82.online', 1298530968, -4974303698, 'private', true, true, '2025-09-20', NULL, NOW(), NOW()),
('https://prospect-82.ru', 'prospect-82.ru', 1298530968, -4974303698, 'private', true, true, '2025-09-20', NULL, NOW(), NOW()),
('https://проспект-82.рф', 'проспект-82.рф', 1298530968, -4974303698, 'private', true, true, '2026-08-22', NULL, NOW(), NOW()),

-- Домен с доменом и хостингом - prospect82.ru (исправлено: убрана дублирующаяся запись)
('https://prospect82.ru', 'prospect82.ru', 1298530968, -4974303698, 'private', true, true, '2026-08-22', '2025-09-14', NOW(), NOW());

-- Проверка добавленных записей
SELECT 
    id,
    original_url,
    domain_expires_at,
    created_at
FROM botmonitor_sites 
WHERE original_url IN (
    'прогрэсс.рф', 'прогрэс.рф', 'про-гресс.рф', 'жкпрогресс.рф',
    'жкалькор.рф', 'жк-алькор.рф', 'алькор82.рф', 'jkalkor.ru',
    'progres82.ru', 'бархат-новыйсвет.рф'
)
ORDER BY domain_expires_at, original_url;
