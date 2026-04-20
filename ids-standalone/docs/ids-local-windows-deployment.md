# IDS Windows Local Deployment

This guide is for the "no cloud server yet" stage.

It assumes:

- the standalone IDS code lives at `D:\ids\ids-standalone`
- you are using a Windows machine
- you want to run IDS locally first, then connect the future site later

## What You Can Do Without a Server

You can already run a full local IDS workstation:

- backend on your own PC
- frontend on your own PC
- local SQLite database
- upload audit and quarantine
- IDS event review and alert center
- email / webhook / WeCom notifications
- future site integration through `POST /api/upload` and `POST /api/ids/events/ingest`

What you do **not** get yet:

- 24x7 online protection after your PC is shut down
- public internet hosting by itself
- host-wide traffic capture for all software on the machine

## Recommended Local Layout

```text
D:\ids\
  gongyinglian\
    workspace\
      CampusSupplyChainSecurityPlatform\
  ids-standalone\
```

## Prerequisites

Install these once on the local machine:

- Python 3.10+
- Node.js 18+

Optional:

- a mailbox SMTP account for alert email
- an AI provider key if you want LLM-assisted upload audit

## One-Click Local Start

From `D:\ids\ids-standalone`:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-ids.ps1
```

Or just double-click:

```text
start-ids.bat
```

What the startup script now does:

- checks Python and npm
- auto-installs backend Python dependencies if they are missing
- auto-installs frontend dependencies on first run
- initializes `ids-backend\ids.db`
- migrates legacy IDS data from the old monolith if it is found
- starts backend on `127.0.0.1:8170`
- starts frontend on `127.0.0.1:5175`

Default login:

- username: `ids_admin`
- password: `123456`

## Local Health Check

Use this anytime you want to confirm whether the environment is ready:

```powershell
powershell -ExecutionPolicy Bypass -File .\check-ids-local.ps1
```

It checks:

- Python
- npm
- backend package readiness
- frontend `node_modules`
- backend/frontend ports
- backend/frontend local HTTP endpoints

## Email Alerts

You do not need to build your own mail server.

Use a normal SMTP account such as:

- QQ mail
- 163 mail
- enterprise mail
- any SMTP relay you already own

See:

- [ids-notification-setup.md](/D:/ids/ids-standalone/docs/ids-notification-setup.md)

## Future Site Integration

When the new site is ready, connect it to the standalone IDS with:

- `POST /api/upload`
- `POST /api/ids/events/ingest`

If the site and IDS are both running on your local machine during development,
the site can call the local IDS directly.

If the site later moves to another always-on machine, move the standalone IDS to
that machine too, or expose the IDS service to the internal network.

## Reality Check

Local-only deployment is good for:

- development
- feature completion
- integration testing
- operator workflow rehearsal
- demo use

For real long-running production use, you still eventually need an always-on
machine, even if it is not a cloud server.
