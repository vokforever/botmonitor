-- SQL-скрипт для массового добавления доменов с датами истечения домена и хостинга
-- Выполните этот скрипт в Supabase SQL Editor

-- Вставка доменов с датами истечения домена и хостинга
-- Замените {CHAT_ID} и {USER_ID} на реальные значения

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
('https://прогрэсс.рф', 'прогрэсс.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://прогрэс.рф', 'прогрэс.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://про-гресс.рф', 'про-гресс.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),
('https://жкпрогресс.рф', 'жкпрогресс.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-03-30', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 13.05.2026 (БЕЗ хостинга)
('https://жкалькор.рф', 'жкалькор.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://жк-алькор.рф', 'жк-алькор.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://алькор82.рф', 'алькор82.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),
('https://jkalkor.ru', 'jkalkor.ru', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-13', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 27.04.2026 (БЕЗ хостинга)
('https://progres82.ru', 'progres82.ru', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-04-27', NULL, NOW(), NOW()),

-- Домены с датой истечения домена 03.05.2026 (БЕЗ хостинга)
('https://миндаль.рус', 'миндаль.рус', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://кварталминдаль.рф', 'кварталминдаль.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://квартал-миндаль.рф', 'квартал-миндаль.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://жк-миндаль.рф', 'жк-миндаль.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),
('https://kvartal-mindal.ru', 'kvartal-mindal.ru', {USER_ID}, {CHAT_ID}, 'private', true, true, '2026-05-03', NULL, NOW(), NOW()),

-- Домен без даты истечения домена и хостинга (бархат-новыйсвет.рф)
('https://бархат-новыйсвет.рф', 'бархат-новыйсвет.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, NULL, NULL, NOW(), NOW()),

-- Домены ТОЛЬКО с хостингом (vladograd.com, жкпредгорье.рф) - 02.07.2026 (296 дней с 11.09.2025)
('https://vladograd.com', 'vladograd.com', {USER_ID}, {CHAT_ID}, 'private', true, true, NULL, '2026-07-02', NOW(), NOW()),
('https://жкпредгорье.рф', 'жкпредгорье.рф', {USER_ID}, {CHAT_ID}, 'private', true, true, NULL, '2026-07-02', NOW(), NOW());

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
