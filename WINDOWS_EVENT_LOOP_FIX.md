# Исправление предупреждения Proactor Event Loop в Windows

## Проблема

При запуске бота мониторинга на Windows возникало предупреждение:
```
RuntimeWarning: Proactor event loop does not implement add_reader family of methods required.
Registering an additional selector thread for add_reader support.
To avoid this warning use:
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
```

Это предупреждение связано с использованием библиотеки `curl_cffi` и особенностями работы asyncio в Windows.

## Решение

Добавлена настройка event loop политики для Windows во всех файлах, использующих asyncio:

```python
# Исправление для Windows Proactor event loop предупреждения
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

## Обновленные файлы

1. `main.py` - основной файл бота
2. `test_layered_health_check.py` - тестирование Layered Health Check
3. `test_403_scenario.py` - тестирование сценария с 403 Forbidden
4. `whois_watchdog.py` - модуль WHOIS мониторинга
5. `whois_integration.py` - интеграция WHOIS в основной бот

## Результат

- ✅ Устранено предупреждение при запуске на Windows
- ✅ Сохранена функциональность бота
- ✅ Совместимость с другими ОС (код выполняется только на Windows)

## Примечания

- Это изменение не влияет на функциональность бота
- Код автоматически определяет ОС и применяет исправление только для Windows
- Для Linux и macOS никаких изменений не требуется