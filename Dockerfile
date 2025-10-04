# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# optional but handy
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ✅ install from the real requirements file path
COPY rag/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r /tmp/requirements.txt gunicorn

# bring in the rest of the code
COPY . .

EXPOSE 8000
# run Flask via gunicorn, bind to all interfaces
CMD ["gunicorn", "-b", "0.0.0.0:8000", "server.app:app"]
