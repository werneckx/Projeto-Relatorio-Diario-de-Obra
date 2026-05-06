FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim-bookworm

WORKDIR /app

ENV FLASK_APP=run.py
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WKHTMLTOPDF_CMD=/usr/bin/wkhtmltopdf

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-mysql-client \
        fonts-dejavu-core \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libjpeg62-turbo \
        libopenjp2-7 \
        wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

EXPOSE 5000

CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120"]
