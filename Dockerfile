# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# lightweight but handy for checks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt gunicorn

# App code
COPY . .

EXPOSE 8000
# Run Flask app; binds to all interfaces inside the container
CMD ["gunicorn", "-b", "0.0.0.0:8000", "server.app:app"]
