FROM python:3.11-slim
WORKDIR /app

COPY ml/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ml/ ./ml/

# ML inference service - to be implemented
# CMD ["python", "-m", "ml.inference.service"]
CMD ["echo", "ML service placeholder"]
