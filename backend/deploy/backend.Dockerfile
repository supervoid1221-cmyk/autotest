FROM docker.m.daocloud.io/library/python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright \
    PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000

WORKDIR /app

RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        curl \
        fonts-noto-cjk \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt gunicorn==23.0.0 \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN mkdir -p /app/logs /app/screenshots /app/temps /app/upload_yaml \
        /app/uploaded_api_files /app/runtime_auth_locks

EXPOSE 8000

CMD ["gunicorn", "Tesla.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "3600", "--access-logfile", "-", "--error-logfile", "-"]
