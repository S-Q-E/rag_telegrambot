FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY ../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код API
COPY . .

# Модель для эмбеддингов будет скачана при первом запуске
# Убедитесь, что у сервера есть доступ в интернет для этого
