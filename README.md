Інструкція для запуску застосунку.
### API IGDB
Для роботи функціоналу IGDB необхідно додати API ключі в файлі inventory/views.py. Детальніше про отримання ключів: https://api-docs.igdb.com/#getting-started.
Це зміні, а саме CLIENT_ID і CLIENT_SECRET розтащовані у стрічках 77,78 файлу views.py. Також можна вказати нище наведені ключі для тестування до вищезгаданого файлу:
```
CLIENT_ID = 'a37e2nsz0y0ala5q3u1ydl19bfetrk' 
CLIENT_SECRET = 'ct9jp4ju08maqdim03v4d59lworthr'
```

### Запуск через Docker
Також у разі використання Docker для розгортання необхідно створити файл з назвою .env у корневій директорії проекту(де знаходится файл manage.py та Dockerfile) та вказати свої значення зміних для налаштування бази даних та django. Як робочий приклад можна використати код наведений нижче:
  
```
POSTGRES_DB=retro_db
POSTGRES_USER=retro_user
POSTGRES_PASSWORD=SuperSecretRetroPassword2026
POSTGRES_HOST=db
POSTGRES_PORT=5432
SECRET_KEY=django-insecure-super-long-random-string-12345
DEBUG=False
```
Після чого розгорнути проект у докер: 
```
docker compose up
```
