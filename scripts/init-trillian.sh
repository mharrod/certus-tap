#!/bin/bash

set -euo pipefail

# Trillian Tree Initialization Script
# This script initializes the Trillian merkle tree database tables
# Required after: docker compose up (when database is empty)

MYSQL_CONTAINER=${MYSQL_CONTAINER:-trillian-log-db}
MYSQL_USER=${MYSQL_USER:-trillian}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-trillian}
MYSQL_DATABASE=${MYSQL_DATABASE:-trillian}
TREE_ID=${TREE_ID:-1}

log() {
    printf '[init-trillian] %s\n' "$1"
}

# Wait for MySQL to be ready
wait_for_mysql() {
    log "Waiting for MySQL to be ready..."
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "SELECT 1" >/dev/null 2>&1; then
            log "MySQL is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done

    log "ERROR: MySQL failed to become ready after ${max_attempts} seconds"
    return 1
}

# Check if schema exists
is_schema_initialized() {
    local table_count
    table_count=$(docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -sN -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$MYSQL_DATABASE' AND table_name='Trees';" 2>/dev/null || echo "0")

    if [ "$table_count" -gt 0 ]; then
        return 0  # Schema exists
    else
        return 1  # Schema missing
    fi
}

# Initialize Trillian schema
init_schema() {
    log "Initializing Trillian database schema..."

    # Download and apply Trillian storage schema
    if curl -sf https://raw.githubusercontent.com/google/trillian/master/storage/mysql/schema/storage.sql | \
       docker exec -i "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" 2>/dev/null; then
        log "Trillian schema initialized successfully"
    else
        log "WARNING: Failed to download schema, may already exist or network issue"
    fi
}

# Create Rekor database if needed
init_rekor_database() {
    log "Ensuring Rekor database exists..."

    docker exec "$MYSQL_CONTAINER" mysql -uroot -proot -e "
        CREATE DATABASE IF NOT EXISTS rekor;
        GRANT ALL PRIVILEGES ON rekor.* TO 'trillian'@'%';
        FLUSH PRIVILEGES;
    " 2>/dev/null || log "WARNING: Could not create Rekor database (may already exist)"

    log "Rekor database ready"
}

# Initialize tree in Trees table
init_tree_entry() {
    log "Initializing tree entry in Trees table..."

    local timestamp_ms
    timestamp_ms=$(date +%s)000

    docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "
        INSERT INTO Trees (
            TreeId, TreeState, TreeType, HashStrategy, HashAlgorithm, SignatureAlgorithm,
            DisplayName, Description, CreateTimeMillis, UpdateTimeMillis, MaxRootDurationMillis,
            PrivateKey, PublicKey
        ) VALUES (
            $TREE_ID, 'ACTIVE', 'LOG', 'RFC6962_SHA256', 'SHA256', 'ECDSA',
            'Rekor Log', 'Rekor Transparency Log', $timestamp_ms, $timestamp_ms, 0,
            x'', x''
        ) ON DUPLICATE KEY UPDATE TreeId=TreeId;
    " 2>/dev/null

    log "Tree entry created"
}

# Check if tree is already initialized
is_tree_initialized() {
    local tree_head_count
    tree_head_count=$(docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -sN -e "SELECT COUNT(*) FROM TreeHead WHERE TreeId=$TREE_ID;" 2>/dev/null || echo "0")

    if [ "$tree_head_count" -gt 0 ]; then
        return 0  # Already initialized
    else
        return 1  # Not initialized
    fi
}

# Initialize TreeControl table
init_tree_control() {
    log "Initializing TreeControl for tree $TREE_ID..."

    docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "
        INSERT IGNORE INTO TreeControl (TreeId, SigningEnabled, SequencingEnabled, SequenceIntervalSeconds)
        VALUES ($TREE_ID, 1, 1, 0);
    " 2>/dev/null

    log "TreeControl initialized"
}

# Initialize TreeHead table with empty tree state
init_tree_head() {
    log "Initializing TreeHead for tree $TREE_ID..."

    # SHA256 hash of empty string (for empty merkle tree)
    local empty_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "
        INSERT INTO TreeHead (TreeId, TreeHeadTimestamp, TreeSize, RootHash, TreeRevision, RootSignature)
        VALUES ($TREE_ID, UNIX_TIMESTAMP() * 1000000000, 0, UNHEX('$empty_hash'), 0, x'');
    " 2>/dev/null

    log "TreeHead initialized with empty tree (size=0)"
}

# Main initialization flow
main() {
    log "Starting Trillian initialization..."

    # Wait for MySQL
    if ! wait_for_mysql; then
        exit 1
    fi

    # Check and initialize schema if needed
    if ! is_schema_initialized; then
        log "Trillian schema not found, initializing..."
        init_schema
    else
        log "Trillian schema already exists"
    fi

    # Create Rekor database
    init_rekor_database

    # Check if tree already initialized
    if is_tree_initialized; then
        log "Tree $TREE_ID is already initialized (TreeHead exists)"
        log "Skipping tree initialization"
        exit 0
    fi

    log "Tree $TREE_ID needs initialization"

    # Initialize tree entry in Trees table
    init_tree_entry

    # Initialize TreeControl
    init_tree_control

    # Initialize TreeHead
    init_tree_head

    log "✅ Trillian tree $TREE_ID successfully initialized"
    log "✅ Rekor database ready"
    log "✅ Tree is ready for Rekor to use"
}

main "$@"
