# IDS Standalone Workspace

This folder is the cleaned standalone root for the contents extracted from `IDS-2026-04-14.zip`.

## Layout

- `ids-backend/`: FastAPI-based IDS backend
- `ids-frontend/`: Vue/Vite-based IDS frontend
- `docs/`: split notes, changelog, and architecture documents
- `start-ids.ps1`: local Windows startup script
- `.env.ids.example`: environment template
- `docker-compose.ids.yml`: local container composition

## Why This Folder Exists

The ZIP was originally extracted directly into `D:\ids`, which mixed standalone IDS files with the monolith workspace and archive files. The standalone package now lives under its own root so development, packaging, migration, and deployment can be handled independently.

## Local Start

From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-ids.ps1
```

Quick local environment check:

```powershell
powershell -ExecutionPolicy Bypass -File .\check-ids-local.ps1
```

Windows local-only deployment guide:

- [ids-local-windows-deployment.md](/D:/ids/ids-standalone/docs/ids-local-windows-deployment.md)
- [ids-notification-setup.md](/D:/ids/ids-standalone/docs/ids-notification-setup.md)

The startup script now tries to auto-detect a legacy monolith at one of these common paths:

```text
..\gongyinglian\workspace\CampusSupplyChainSecurityPlatform
..\CampusSupplyChainSecurityPlatform
```

If the old system lives elsewhere, you can override it:

```powershell
$env:IDS_LEGACY_MONOLITH_ROOT = 'D:\path\to\CampusSupplyChainSecurityPlatform'
powershell -ExecutionPolicy Bypass -File .\start-ids.ps1
```

Or pass a direct database path:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-ids.ps1 -LegacySourceDbPath 'D:\path\to\backend\supply_chain.db'
```

## Recommended Workspace Layout

```text
D:\ids\
  gongyinglian\
    workspace\
      CampusSupplyChainSecurityPlatform\
  ids-standalone\
  archives\
```

Keep archives and handoff ZIPs outside the standalone source tree. Keep runtime data under `ids-data/` in container mode or under `ids-backend/runtime/` only for local development.

## Site Integration

The standalone IDS now supports service-to-service integrations for:

- `POST /api/upload`
- `POST /api/ids/events/ingest`

Set `IDS_INTEGRATION_TOKEN` in the backend environment, then call either endpoint with:

```text
X-IDS-Integration-Token: <your-shared-token>
X-IDS-Source-System: site-gateway
```

Human operators can still use the existing JWT-based IDS login flow.
