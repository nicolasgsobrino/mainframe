FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .
RUN addgroup --system appuser \
    && adduser --system --ingroup appuser appuser \
    && chown -R appuser:appuser /app
USER appuser
