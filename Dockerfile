# ====================================================================
# Stage 1: BUILDER - Installs dependencies and compiles native packages
# ====================================================================
FROM python:3.11-slim AS builder

# Set unbuffered Python output for Docker logging best practice
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install build dependencies required for native Python packages (e.g., psycopg2)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory and copy requirements first to leverage Docker caching
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# ====================================================================
# Stage 2: PRODUCTION - Copies only the application and installed packages
# ====================================================================
FROM python:3.11-slim AS runtime

# Use a non-root user for enhanced security (best practice)
RUN useradd --create-home appuser
USER appuser

# Copy installed Python packages and executables from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# Copy application code and static assets
COPY . /app
WORKDIR /app

# Expose the Gunicorn port (standard for production web servers)
EXPOSE 8000

# Run the application using Gunicorn (the production WSGI server)
# The command starts Gunicorn, binding to 0.0.0.0 on port 8000, and calls your app entry point.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app.main:app"]