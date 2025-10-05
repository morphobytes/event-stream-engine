-- Initial database setup for Event Stream Engine
-- This script runs when the PostgreSQL container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for common queries
-- These will be created by migrations, but having them here ensures consistency

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE event_stream TO postgres;