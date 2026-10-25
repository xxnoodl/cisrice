FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir 'pip>=26.2,<27' && pip install --no-cache-dir . && useradd --uid 10001 --create-home cisrice
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
USER cisrice
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
