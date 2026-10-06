FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=10000 SQUADFINDER_CLOUD=1 SQUADFINDER_SEED_DEMO=0 SQUADFINDER_SEED_CATALOG=0
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 120 --access-logfile -"]
