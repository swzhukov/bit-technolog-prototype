# БИТ.Технолог — production Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8081/health || exit 1

EXPOSE 8081

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081", "--no-access-log", "--log-level", "info", "--proxy-headers", "--forwarded-allow-ips=*", "--root-path", "/bit-technolog"]
