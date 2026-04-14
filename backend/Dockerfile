FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    fonts-noto-cjk \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY alembic.ini .
COPY backend/ backend/
COPY tests/ tests/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "backend.start"]
