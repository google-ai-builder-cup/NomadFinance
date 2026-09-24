# syntax=docker/dockerfile:1

# Matches the team's local interpreter (3.11.9) so dev and prod behave the same.
FROM python:3.11.9-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.11.9-slim-bookworm AS runtime

# Gunicorn reads PORT for its bind address and WEB_CONCURRENCY for its worker count,
# so Cloud Run can override both without a rebuild.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080 \
    WEB_CONCURRENCY=1

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser app ./app

USER appuser
EXPOSE 8080

# Cloud Run enforces request timeouts itself; timeout 0 stops gunicorn killing slow Gemini calls.
CMD ["gunicorn", "app.main:app", "--worker-class", "uvicorn_worker.UvicornWorker", "--timeout", "0"]
