# IDS Delivery Bundle

This repository now contains only IDS-related delivery content:

- `ids-standalone/`: standalone IDS source code
- `ids-docker-package/`: Docker delivery package for deployment

## Startup Entry Points

- `ids-docker-package/start-ids-docker.ps1`
- `ids-docker-package/start-ids-docker.sh`

These are the unified IDS Docker deployment entrypoints.

## Frontend Configuration Scope

After IDS is deployed once, the frontend can directly complete these runtime operations:

- edit communication settings
- edit default upstream target IP and port
- edit host mappings and extra site mappings
- view HTTP session monitoring records
- view captured request and response details
- manually block or unblock source IPs

If you change Docker host port exposure, or add a new external ingress port that must be published by Docker, run the Docker startup entrypoint again so Compose port mappings are regenerated.

## Notes

- Runtime databases, generated logs, local `.env` files, and generated Docker compose outputs are excluded from version control.
- IDS frontend configuration writes back to runtime config and state files instead of being display-only.
