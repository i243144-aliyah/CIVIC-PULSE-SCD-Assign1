# syntax=docker/dockerfile:1
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f AS builder

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  VIRTUAL_ENV=/opt/venv \
  PATH="/opt/venv/bin:$PATH"

WORKDIR /build
RUN python -m venv /opt/venv

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools==84.0.0 \
  && pip install --no-cache-dir -r requirements.txt \
  && pip uninstall --yes pip setuptools

FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f AS runtime

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  VIRTUAL_ENV=/opt/venv \
  PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN groupadd --gid 10001 appuser \
  && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 app /app/app
COPY --chown=10001:10001 alembic /app/alembic
COPY --chown=10001:10001 alembic.ini /app/alembic.ini

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
