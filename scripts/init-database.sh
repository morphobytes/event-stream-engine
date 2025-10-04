#!/bin/bash

# Database initialization script for Event Stream Engine
set -e

echo "Starting database initialization..."

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
until docker compose exec -T db pg_isready -U dev_user -d event_stream_dev; do
  sleep 2
done
echo "PostgreSQL ready"

# Initialize Flask-Migrate
if [ ! -d "migrations" ]; then
    echo "Initializing Flask-Migrate..."
    docker compose exec web flask db init
else
    echo "Migration repository exists"
fi

# Generate migration
echo "Generating migration..."
docker compose exec web flask db migrate -m "Initial schema setup"

# Apply migration
echo "Applying migration..."
docker compose exec web flask db upgrade

# Verify schema
echo "Verifying schema..."
docker compose exec -T db psql -U dev_user -d event_stream_dev -c "\dt"

echo "Database initialization complete"