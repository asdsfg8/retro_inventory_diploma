# Використовуємо офіційний легкий образ Python
FROM python:3.13-slim

# Встановлюємо робочу директорію в контейнері
WORKDIR /app

# Копіюємо файл залежностей та встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проєкту в контейнер
COPY . .

# Відкриваємо порт 8000
EXPOSE 8000

# Запускаємо Gunicorn (бойовий сервер)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "core.wsgi:application"]
