# Trillian Tree Initialization

## Overview

The Trillian merkle tree requires database initialization after the MySQL database is created. This happens automatically when you run `just up` or `just rebuild`.

## What Gets Initialized

When you start the stack from scratch, the `init-trillian.sh` script initializes:

1. **TreeControl Table**: Enables signing and sequencing for tree ID 1
2. **TreeHead Table**: Creates the initial empty merkle tree state (size=0, empty root hash)

## Automatic Initialization

The initialization script is automatically called by:

- `just up` - Starts the full stack
- `just rebuild` - Rebuilds and restarts the stack

The script is idempotent - it checks if the tree is already initialized and skips if it is.

## Manual Initialization

If you need to manually initialize the Trillian tree:

```bash
./scripts/init-trillian.sh
```

## When Initialization is Needed

You need to run initialization when:

- Starting the stack for the first time (`just up`)
- After running `just destroy` (which removes volumes including the database)
- After manually deleting the MySQL data volume

You do NOT need to run it when:

- Restarting containers (`docker restart`)
- Running `just down` then `just up` (volumes are preserved)
- The tree is already initialized

## Configuration

The script uses these environment variables (with defaults):

- `MYSQL_CONTAINER=trillian-log-db` - MySQL container name
- `MYSQL_USER=trillian` - Database user
- `MYSQL_PASSWORD=trillian` - Database password
- `MYSQL_DATABASE=trillian` - Database name
- `TREE_ID=1` - Trillian tree ID

## Troubleshooting

### "tree needs initialising" Error

If you see this error in Rekor logs:

```
grpc error: rpc error: code = FailedPrecondition desc = tree needs initialising
```

Run the initialization script manually:

```bash
./scripts/init-trillian.sh
docker restart trillian-log-signer trillian-log-server rekor
```

### Script Fails with MySQL Connection Error

Ensure the MySQL container is running and healthy:

```bash
docker ps --filter "name=trillian-log-db"
docker logs trillian-log-db
```

Wait for MySQL to be ready (the script waits up to 30 seconds automatically).

### Tree Already Initialized

If the script reports the tree is already initialized but Rekor still fails:

1. Check the TreeHead table:
   ```bash
   docker exec trillian-log-db mysql -utrillian -ptrillian trillian -e "SELECT * FROM TreeHead WHERE TreeId=1;"
   ```

2. Restart Trillian services to pick up the state:
   ```bash
   docker restart trillian-log-signer trillian-log-server rekor
   ```

## Integration with Stack

The initialization happens in this sequence during `just up`:

1. Start infrastructure services (MySQL, etc.)
2. Bootstrap datalake
3. Start Sigstore services (Trillian, Rekor)
4. Wait 5 seconds for MySQL to be ready
5. **Run init-trillian.sh** ← Automatic initialization
6. Start application services (Ask, Trust, Assurance, Transform)

This ensures Trillian is properly initialized before Rekor tries to use it.
