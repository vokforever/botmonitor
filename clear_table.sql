-- SQL-скрипт для полной очистки таблицы botmonitor_sites
-- ВНИМАНИЕ: Этот скрипт удалит ВСЕ данные из таблицы!
-- Выполните этот скрипт в Supabase SQL Editor, если хотите начать с чистого листа

-- Показываем количество записей перед удалением
SELECT COUNT(*) as records_before_deletion FROM botmonitor_sites;

-- Удаляем все записи
DELETE FROM botmonitor_sites;

-- Проверяем, что таблица пуста
SELECT COUNT(*) as records_after_deletion FROM botmonitor_sites;

-- Теперь можно выполнить ваш основной скрипт domains_bulk_insert.sql
