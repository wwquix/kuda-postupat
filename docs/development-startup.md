# Side-effect-free development startup

M-DEV-SAFETY-01 makes the existing `start-dev.ps1` workflow safe for read-only
local browser QA. It does not change public API contracts, database schema,
catalog data, monitoring calculations or frontend behavior.

## Configuration contract

The backend setting is:

```env
DEVELOPMENT_SAFE_MODE=false
```

`false` is the application default and the value documented in `.env.example`.
With that default, ordinary non-development startup preserves the established
production behavior: lifespan validates the schema, starts APScheduler and
launches the initial admissions refresh.

`start-dev.ps1` sets `DEVELOPMENT_SAFE_MODE=true` only in the environment
inherited by the child Uvicorn process. It does not edit `.env`, does not place
the value in command-line arguments and restores the previous process-level
environment value before returning to the caller.

The mode is explicit. It is not inferred from host names, ports, debug flags,
the operating system or the presence of Vite.

## Disabled development background work

In development-safe mode FastAPI lifespan still runs the read-only Alembic
revision/schema check, then serves the API without:

- adding or starting the APScheduler admission job;
- creating the automatic startup refresh task;
- opening the BSEU source through that task;
- creating Snapshot, ScraperRun or Notification rows;
- invoking background Telegram delivery.

Existing catalog, university detail, monitoring and status reads remain
available from the main SQLite database. The health response reports
`scheduler_running: false` and the status response has no scheduled next run.

The authenticated `POST /api/refresh` endpoint remains an explicit operator
action and keeps its production behavior. Do not invoke it during read-only QA;
it can fetch upstream data, write runtime rows and deliver Telegram when enabled.

## Zero-side-effect verification

Stop any existing process, record the three runtime tables, start development,
perform only GET/browser navigation, wait past the normal startup-refresh
window, then stop and record the same values again:

```powershell
.\stop-dev.ps1

@'
import json, sqlite3

connection = sqlite3.connect("file:backend/data/admission.db?mode=ro", uri=True)
queries = {
    "snapshots": "SELECT COUNT(*), MAX(id), MAX(fetched_at) FROM admission_snapshots",
    "scraper_runs": "SELECT COUNT(*), MAX(id), MAX(started_at) FROM scraper_runs",
    "notifications": "SELECT COUNT(*), MAX(id), MAX(sent_at) FROM notification_logs",
}
print(json.dumps({name: connection.execute(sql).fetchone() for name, sql in queries.items()}))
connection.close()
'@ | .\.venv\Scripts\python.exe -

.\start-dev.ps1
# Check only GET routes in the browser/API and wait for the former startup window.
.\stop-dev.ps1

# Repeat the same read-only Python block; every value must be identical.
```

Focused automated coverage is in `backend/tests/test_development_startup.py`
and `backend/tests/test_config.py`. Those tests use an isolated temporary SQLite
database and mocks; they do not start the real scheduler, call BSEU or Telegram,
or touch the main database.
