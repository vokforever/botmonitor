-- Миграция для добавления колонки is_reserve_domain в таблицу botmonitor_domain_monitor
-- Выполните этот SQL в вашей базе данных Supabase, если таблица уже существует без этой колонки

-- Добавление колонки is_reserve_domain
ALTER TABLE botmonitor_domain_monitor 
ADD COLUMN IF NOT EXISTS is_reserve_domain BOOLEAN DEFAULT FALSE;

-- Создание индекса для флага резервного домена
CREATE INDEX IF NOT EXISTS idx_botmonitor_domain_monitor_is_reserve ON botmonitor_domain_monitor(is_reserve_domain);

-- Обновление комментария к таблице
COMMENT ON TABLE botmonitor_domain_monitor IS 'Таблица для мониторинга истечения срока действия доменов через WHOIS';