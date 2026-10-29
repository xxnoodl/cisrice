FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 60 --retries 5 'pip>=26.2,<27' && pip install --timeout 60 --retries 5 . && useradd --uid 10001 --create-home cisrice
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
USER cisrice
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
