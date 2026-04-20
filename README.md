# Campus Supply Chain + IDS Export

This repository packages the current campus supply chain project and standalone IDS work into one clean GitHub-ready export.

## Structure

- `campus-supply-chain/`: campus supply chain source code
- `ids-standalone/`: standalone IDS source code
- `runtime/startup/`: startup and configuration scripts
- `docs/`: startup and deployment notes
- `design-preview/`: current IDS dashboard preview page
- `start-campus-ids.bat`: launcher wrapper

## Notes

- Real `.env` files and runtime databases were intentionally excluded.
- Use the included example environment files and fill in your own values before deployment.
- Python virtual environments, caches, nested `.git` directories, and runtime artifacts were excluded to keep the repository clean.
