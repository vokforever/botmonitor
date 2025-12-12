# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем системные зависимости, которые могут понадобиться для WHOIS и SSL
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Обновляем pip и устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Открываем порт (CapRover автоматически назначит порт)
EXPOSE 3000

# Команда запуска
CMD ["python", "main.py"]
