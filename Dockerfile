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

# Initialize database schema (add missing columns/tables), stamp alembic, then start server
CMD ["sh", "-c", "python scripts/init_db.py && alembic stamp head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"]
