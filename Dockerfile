# Multi-stage build for production-ready size optimization

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies (for building generic wheels if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# Stage 2: Final Image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (e.g. libpq for psycopg2 if needed)
# RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy built wheels from builder
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install dependencies
RUN pip install --no-cache /wheels/*

# Copy application code
COPY . .

# Environment setup
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run with the new entry point
CMD ["python", "run.py"]
