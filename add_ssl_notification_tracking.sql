-- Добавление колонок для отслеживания последнего дня отправки уведомлений
-- Это предотвратит дублирование уведомлений в течение одного дня

ALTER TABLE botmonitor_sites 
ADD COLUMN ssl_last_notification_day DATE,
ADD COLUMN domain_last_notification_day DATE,
ADD COLUMN hosting_last_notification_day DATE;

-- Добавляем комментарии к колонкам
COMMENT ON COLUMN botmonitor_sites.ssl_last_notification_day IS 'Дата последней отправки SSL уведомления для предотвращения дублирования';
COMMENT ON COLUMN botmonitor_sites.domain_last_notification_day IS 'Дата последней отправки уведомления о домене для предотвращения дублирования';
COMMENT ON COLUMN botmonitor_sites.hosting_last_notification_day IS 'Дата последней отправки уведомления о хостинге для предотвращения дублирования';
