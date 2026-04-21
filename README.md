# Campus Supply Chain Security Bundle

This repository now contains the cleaned delivery layout for the current delivery set:

- `campus-supply-chain/`: campus supply chain source
- `ids-standalone/`: standalone IDS source
- `ids-docker-package/`: Docker delivery package for IDS
- `runtime/startup/`: Windows startup scripts

## Startup Entry Points

- `start-supply-chain.bat`
  Starts only the campus supply chain frontend and backend.
- `ids-docker-package/start-ids-docker.ps1`
- `ids-docker-package/start-ids-docker.sh`
  Unified IDS Docker deployment entrypoints.

## Notes

- The old mixed `start-campus-ids` chain has been removed.
- IDS communication settings are saved from the IDS frontend and written to runtime config/state files.
- Generated databases, live logs, local `.env` files, and transient Docker outputs are intentionally excluded from version control.
