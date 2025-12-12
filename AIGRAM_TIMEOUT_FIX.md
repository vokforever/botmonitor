# Исправление ошибки TypeError в aiogram

## Проблема
При запуске бота мониторинга сайтов возникала ошибка:
```
TypeError: unsupported operand type(s) for +: 'ClientTimeout' and 'int'
```

## Причина
Ошибка возникала из-за несовместимости типов при инициализации бота с кастомной сессией:
```python
session = AiohttpSession(timeout=ClientTimeout(total=60, connect=15))
bot = Bot(token=API_TOKEN, session=session)
```

Внутренняя реализация aiogram пыталась сложить объект `ClientTimeout` с числовым значением `polling_timeout`, что вызывало ошибку.

## Решение
Удалена кастомная сессия при инициализации бота. Вместо этого используется стандартная инициализация:

```python
# Было:
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientTimeout

session = AiohttpSession(timeout=ClientTimeout(total=60, connect=15))
bot = Bot(token=API_TOKEN, session=session)

# Стало:
from aiohttp import ClientTimeout  # Импорт оставлен для других частей кода

bot = Bot(token=API_TOKEN)
```

## Результат
Бот теперь запускается без ошибок и корректно работает с polling.

## Примечания
- Остальные использования `ClientTimeout` в коде (для aiohttp.ClientSession) остаются без изменений
- Если в будущем потребуется настройка таймаутов для бота, это нужно делать через параметры самого Bot, а не через сессию