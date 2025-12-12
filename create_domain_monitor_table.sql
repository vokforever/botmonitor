-- Миграция для создания таблицы botmonitor_domain_monitor
-- Выполните этот SQL в вашей базе данных Supabase

-- Создание таблицы botmonitor_domain_monitor для WHOIS Watchdog
CREATE TABLE IF NOT EXISTS botmonitor_domain_monitor (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    domain_name VARCHAR(255) NOT NULL UNIQUE,
    current_expiry_date DATE NOT NULL,
    admin_chat_id BIGINT NOT NULL,
    project_chat_id BIGINT NOT NULL,
    is_reserve_domain BOOLEAN DEFAULT FALSE,
    last_check_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Создание индекса для быстрого поиска по домену
CREATE INDEX IF NOT EXISTS idx_botmonitor_domain_monitor_domain_name ON botmonitor_domain_monitor(domain_name);

-- Создание индекса для даты последней проверки
CREATE INDEX IF NOT EXISTS idx_botmonitor_domain_monitor_last_check_date ON botmonitor_domain_monitor(last_check_date);

-- Создание индекса для флага резервного домена
CREATE INDEX IF NOT EXISTS idx_botmonitor_domain_monitor_is_reserve ON botmonitor_domain_monitor(is_reserve_domain);

-- Добавление комментария к таблице
COMMENT ON TABLE botmonitor_domain_monitor IS 'Таблица для мониторинга истечения срока действия доменов через WHOIS';