-- Initialize databases for Sigstore services
-- This script runs automatically when the MySQL container starts for the first time

-- Create trillian database for Trillian Log Server
CREATE DATABASE IF NOT EXISTS trillian;
GRANT ALL PRIVILEGES ON trillian.* TO 'trillian'@'%';

-- Create rekor database for Rekor search index
CREATE DATABASE IF NOT EXISTS rekor;
GRANT ALL PRIVILEGES ON rekor.* TO 'trillian'@'%';

FLUSH PRIVILEGES;
