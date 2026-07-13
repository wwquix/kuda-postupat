# Modular monolith for the first platform release

## Status
Accepted

## Context

The application already runs as one FastAPI process with SQLAlchemy, SQLite and an in-process APScheduler, while Nginx serves the static React build. Production is limited to roughly 1 vCPU and 2 GB RAM. The redesign adds several domains, but does not need independently scaled services or an external message broker.

## Decision

Keep one deployable backend and split it internally into `api`, `adapters`, `models`, `schemas`, `services`, `repositories`, `cli` and `core`. Domain boundaries are enforced through DTOs and service/repository interfaces. Keep one Uvicorn worker so one scheduler owns jobs. Nginx continues to serve frontend assets and proxy `/api`.

## Consequences

- Deployment, backups, transactions and local development remain simple.
- Domain code can evolve without preserving the current `main.py`/`scraper.py` concentration.
- Internal boundaries require tests and review because process isolation does not enforce them.
- Long source calls need bounded async I/O and short SQLite transactions.
- A future split remains possible only if measured load demonstrates it; it is not pre-built.

## Alternatives considered

- Microservices: rejected due to VPS cost, operational overhead and premature distributed consistency problems.
- Separate scheduler/worker service with Redis or a queue: rejected because one worker and bounded jobs are sufficient.
- Keep all backend code in the existing flat modules: rejected because growing domains would increase coupling and migration risk.
