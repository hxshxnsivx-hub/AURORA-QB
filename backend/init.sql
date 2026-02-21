-- Initialize pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create initial schema
CREATE SCHEMA IF NOT EXISTS aurora_assess;

-- Set search path
SET search_path TO aurora_assess, public;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA aurora_assess TO aurora_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA aurora_assess TO aurora_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA aurora_assess TO aurora_user;
