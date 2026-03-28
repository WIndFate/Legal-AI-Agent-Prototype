FROM python:3.11-slim

ARG INSTALL_LOCAL_OCR=false

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    fonts-noto-cjk \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY alembic.ini .
COPY backend/ backend/
COPY tests/ tests/

RUN if [ "$INSTALL_LOCAL_OCR" = "true" ]; then \
      pip install --no-cache-dir ".[local-ocr]"; \
    else \
      pip install --no-cache-dir .; \
    fi

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
