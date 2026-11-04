# --- Образ Python для bookshop_py ---
FROM python:3.12-slim

# Рабочая директория
WORKDIR /app

# Зависимости (кэш слоя)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения и frontend
COPY app ./app
COPY frontend ./frontend

# Порт приложения
EXPOSE 8000

# Запуск
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]