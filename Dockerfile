FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Create tables and start server
CMD ["sh", "-c", "python -c 'from app.infrastructure.database.connection import Base, engine; import asyncio; from app.infrastructure.database import models; asyncio.run(engine.dispose())' && python scripts/init_db.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"]
