FROM python:3.11-slim

WORKDIR /app

# ให้ subprocess ของ uvicorn --reload หา package `app` ได้ (มิฉะนั้น SpawnProcess แตกตอน import app.main)
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

