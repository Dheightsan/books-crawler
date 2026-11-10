FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY crawler ./crawler
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 crawler \
    && mkdir /data \
    && chown crawler /data

USER crawler
WORKDIR /data
ENTRYPOINT ["python", "-m", "crawler"]
CMD ["--help"]
