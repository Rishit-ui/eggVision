FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

COPY backend ./backend
COPY ml ./ml

RUN useradd -m myuser && mkdir -p /app/backend/uploads && chmod +x /app/backend/docker-entrypoint.sh && chown -R myuser:myuser /app
USER myuser

EXPOSE 8000
WORKDIR /app/backend
ENV PYTHONPATH=/app/backend:/app
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
