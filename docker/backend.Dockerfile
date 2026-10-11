FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

COPY backend ./backend
COPY ml ./ml

RUN useradd -m myuser && mkdir -p /app/backend/uploads && chmod +x /app/backend/docker-entrypoint.sh && chown -R myuser:myuser /app
USER myuser

EXPOSE 8000
WORKDIR /app/backend
ENV PYTHONPATH=/app
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
