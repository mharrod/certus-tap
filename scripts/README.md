# Scripts

Utility scripts for working with the Certus TAP development stack.

- `start-up.sh`: Spins up the full docker-compose stack (OpenSearch, LocalStack, MLflow, backend).
- `preflight.sh`: Runs post-start checks against the running stack (health endpoints and a smoke query).
- `cleanup.sh`: Stops containers and removes the compose project (volumes are retained).
- `destroy.sh`: Fully tears down the stack, deleting named volumes and local upload artifacts.
- `colima-start.sh`: Convenience wrapper that launches the Colima VM with sane defaults via `scripts/local/start-colima.sh`.
- `datalake-upload-sample.sh`: Sends the baked-in `samples/datalake-demo` directory to the LocalStack raw bucket for quick testing.

Run them from the repo root, e.g.:

```
./scripts/start-up.sh
./scripts/preflight.sh
./scripts/cleanup.sh      # stop containers, keep data
./scripts/destroy.sh      # wipe everything
```
