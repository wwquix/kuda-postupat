# Final integration readiness audit

- **Milestone:** `M-READINESS-AUDIT-01`
- **Audit date:** 2026-07-15
- **Audited commit:** `b41ec14 feat: add program detail page`
- **Branch:** `feature/platform-redesign`
- **Decision:** **BLOCKED** — the repository is not ready to begin roadmap section 13 because required first-release feature prerequisites are missing.
- **Selected next milestone:** `M-BSEU-ADAPTER-01` — complete roadmap section 4, “BSEU adapter extraction and registry”, with behavioral parity.

This was a read-only implementation audit. No application code, deployment file,
migration, configuration, frontend, production data or public contract was changed.
Only this report and the minimal roadmap status note were added.

## 1. Scope and source precedence

Evidence was evaluated in this order:

1. executed repository commands, current code/configuration/tests/deployment files,
   runtime HTTP/browser behavior and read-only SQLite inspection;
2. `AGENTS.md` and `docs/roadmap.md`;
3. other repository documentation.

Roadmap statements were not accepted when the current implementation differed.
In particular, the Codebase Memory graph still described the pre-router frontend,
while `frontend/src/App.tsx` contains the current catalog and detail routes.

Section 13 requires integration regression, query/load budgets,
backup/restore/migration rehearsal, Nginx/systemd/base-path validation,
privacy/log review, operator documentation and compatibility/deprecation review.
It explicitly defers destructive migration F, new admission adapters and
infrastructure replacement. Its completion requires a documented go/no-go and
rollback decision, no unresolved high-risk issue, preserved BSEU compatibility,
and separately authorized production deployment.

## 2. Preflight

| Check | Executed result |
|---|---|
| Repository path | Exists and resolves to the requested repository |
| Git root | Matches the requested repository |
| Branch | `feature/platform-redesign` |
| Initial tree | Clean |
| HEAD | `b41ec14 feat: add program detail page` |
| Previous commits | `3105710`, `78f4f08`, `a3b44e2` |
| Unchanged baseline | `check.ps1` passed before documentation changes |

All required context documents named by the milestone were read. Roadmap section
13 contains no direct links to additional documents beyond the repository-wide
deployment and architecture material already inspected.

## 3. Codebase Memory map and native fallbacks

Codebase Memory was used before broad native inspection. No indexing or graph
artifact writes were performed.

Useful calls:

- `get_architecture` for overview, entry points, routes, boundaries, layers,
  clusters and hotspots;
- `search_graph` for lifecycle/database/scheduler/scraper/Telegram/configuration,
  frontend request paths, deployment-related code and critical tests;
- focused `search_graph` patterns for
  `lifespan|scheduled_refresh|manual_refresh|health|get_settings|init_db`,
  `AdmissionScraper|send_once|scheduler`, recommendations, profiles/favorites,
  watchlists and Telegram;
- `trace_path` outbound from `backend.app.main.lifespan` and both directions from
  `backend.app.telegram.send_once`;
- `get_code_snippet` for `lifespan`, `init_db`, `get_settings`,
  `AdmissionScraper.refresh` and `send_once`.

Graph findings verified in exact source:

- `backend/app/main.py::lifespan` validates the schema before serving; safe mode
  yields without a scheduler or initial refresh; normal mode registers one
  coalescing job with `max_instances=1`, starts the scheduler, starts one initial
  refresh task, cancels that task on shutdown and shuts the scheduler down;
- `backend/app/database.py::init_db` calls only the schema-head guard and does not
  run migrations or `create_all`;
- `backend/app/scraper.py::AdmissionScraper.refresh` still owns the production BSEU
  orchestration, persistence and Telegram path;
- `backend/app/telegram.py::send_once` skips disabled delivery, uses persistent
  fingerprint deduplication, sanitizes transport failures and writes a
  notification record only after success;
- no recommendation, anonymous-profile/favorite, or watchlist implementation was
  found; the Telegram code is the legacy owner path.

Native fallbacks were required because the graph was stale/incomplete for recently
added frontend routes and nested Program detail. Exact files were read directly,
and `rg --files`/`rg` were used for non-code files, literal contracts, test names
and the absence of `backend/app/adapters/`. The failed initial graph trace for the
short name `AdmissionScraper.refresh` was recovered with a focused graph search and
the fully qualified symbol. This MCP limitation did not affect the audit.

## 4. Roadmap prerequisite matrix

The section 13 dependency graph directly requires M7, M9 and M12. M9 transitively
requires M4 and M8. The full first-release sequence is listed to avoid treating
completed UI slices as proof that their missing backend prerequisites exist.

| Roadmap milestone | Status | Evidence and consequence |
|---|---|---|
| M1 Architecture/migration design | VERIFIED | Architecture, migration plan, adapter contract and ADRs exist and match the additive SQLite direction. |
| M2 Alembic/catalog schema | VERIFIED | Alembic current/head is `0003_backfill_bseu_catalog`; migration tests cover fresh, legacy, downgrade/re-upgrade and schema guards. |
| M3 BSEU data migration | VERIFIED | Backfill revision and tests preserve legacy rows; the live DB maps the one BSEU Program/Offering and passes integrity/FK checks. |
| M4 BSEU adapter/registry | **MISSING** | There is no `backend/app/adapters/`; production still enters `AdmissionScraper.refresh`. This is a transitive M9 prerequisite. |
| M5 Canonical university import/audit | VERIFIED | Read-only `app.cli audit-catalog` returned `status=ok`, 47 universities, 1 Program, 1 Offering and explicit coverage warnings. |
| M6 Catalog/search API | VERIFIED | Catalog/search routes, OpenAPI assertions, deterministic pagination/filter tests and bounded-query tests passed. |
| M7 Recommendations API | **MISSING** | No recommendation schemas/service/routes/tests exist; only one imported Program/Offering means adequate recommendation data is also absent. Direct M13 dependency. |
| M8 Anonymous profiles/favorites/compare | **MISSING** | No profile, cookie, favorite or compare models/routes/services exist. Transitive M9 prerequisite. |
| M9 Watchlists/Telegram linking | **MISSING** | No profile watchlists/link tokens/per-profile delivery exist; only the legacy owner Telegram path is present. Direct M13 dependency. |
| M10 Frontend shell/homepage | VERIFIED | `BrowserRouter`, base path, shell, homepage and `/monitor` are implemented; tests/build and runtime routes passed. |
| M11 University catalog UI | VERIFIED | `/universities` and its query/filter/pagination behavior are implemented and tested; runtime browser checks passed. |
| M12 University/Program detail UI | VERIFIED | Both real detail routes and nested read-only API contracts exist; tests and runtime browser checks passed. |
| All selected first-release feature milestones | **MISSING** | M4, M7, M8 and M9 are unresolved, so section 13 cannot begin without violating its dependency gate. |

Section 13 outcomes and acceptance evidence:

| Required outcome | Status | Evidence |
|---|---|---|
| Integration regression | VERIFIED | Full unchanged `check.ps1` passed, including live BSEU compatibility. |
| Query/load budgets | PARTIAL | Primary catalog reads have asserted query ceilings; no executed load, memory or disk budget exists. |
| Backup/restore/migration rehearsal | PARTIAL | Scripts and migration tests exist, but no production-like Linux backup/restore/rollback rehearsal was executed. |
| Nginx/systemd/base path | PARTIAL | Templates and one-worker setting exist; no Nginx/systemd/TLS execution was possible on this Windows host. |
| Privacy/log audit | PARTIAL | Tracked-secret pattern scan passed after two test-only tokens were reviewed; raw stored error text is still exposed publicly. |
| Operator docs | PARTIAL | README documents install/update/rollback/logs/backup/restore, but there is no executed go/no-go runbook. |
| Compatibility/deprecation review | PARTIAL | Legacy contract and live tests pass; SQLAlchemy SQLite datetime deprecation warnings remain. |
| Documented go/no-go and rollback | MISSING | This audit provides the no-go decision; production rehearsal and final rollback evidence remain section 13 work. |

## 5. Readiness-domain matrix

| # | Domain | Status | Evidence | Concrete gap and risk | Smallest resolving milestone |
|---:|---|---|---|---|---|
| 1 | Build and automated verification | READY | 105 ordinary backend tests, 1 live test, Ruff, 49 frontend tests, ESLint, TypeScript and Vite build passed. | No blocking gap. Existing Vite chunk warning is P2. | None; maintain the gate. |
| 2 | Environment and secrets | READY | `.env` is ignored; setup/install refuse blind overwrite and generate the manual token; service env is outside the repo with mode 0600; tracked-secret scan found only explicit test tokens. | Operators can still hand-create weak values outside the guarded scripts; verify production env during rehearsal. | M-PROD-REHEARSAL-01. |
| 3 | Schema/Alembic/upgrade | READY | Current=head `0003`; fresh/legacy/downgrade/re-upgrade tests passed; runtime uses a fail-closed schema guard. | No production-like copy was upgraded in this audit, which belongs to the rehearsal domain rather than schema correctness. | M-PROD-REHEARSAL-01. |
| 4 | Backup and restore | PARTIAL | Install/update use SQLite online backup plus integrity/FK checks; README documents restore. | Restore was not rehearsed and no recovery-time/result evidence exists; an untested restore can turn a recoverable failure into data loss/downtime. | M-PROD-REHEARSAL-01. |
| 5 | Production startup/shutdown | PARTIAL | systemd has one worker, graceful timeout, hardening and writable-data isolation; lifespan behavior is tested; dev start/stop was executed. | systemd signals, restart and shutdown were not exercised on Linux. | M-PROD-REHEARSAL-01. |
| 6 | Scheduler/scraper/Telegram | PARTIAL | Safe mode caused zero DB writes and reported scheduler off; tests cover normal lifespan, 304, dedup and sanitized Telegram failure. | Production orchestration remains in the monolithic scraper and the one-worker scheduler was not production-rehearsed; M4/M9 are missing. | **M-BSEU-ADAPTER-01** for the prerequisite; production execution later in M-PROD-REHEARSAL-01. |
| 7 | Nginx/TLS/base path/API routing | PARTIAL | Dedicated server block rewrites base-path API and SPA routes; Vite uses `BASE_URL`; service binds loopback. | Nginx config was not executed, TLS is explicitly left to the operator, and `bash`/`shellcheck` were unavailable. Misrouting or plaintext exposure remains possible. | M-PROD-REHEARSAL-01. |
| 8 | Health and failure visibility | PARTIAL | `/api/health` and `/api/catalog/health` returned 200; catalog health omits internal details; healthcheck script combines HTTP and systemd state. | Legacy `/api/health` and `/api/status` include stored `error_message` values from scraper runs. Public upstream/internal text can disclose operational details. | M-OPS-ERROR-SURFACE-01. |
| 9 | Logging and diagnostics | PARTIAL | Local logs, journald and Nginx log locations are documented; scheduled/manual failures are logged. | `logging.basicConfig` is plain, with no request/run correlation or structured privacy policy; incident diagnosis and redaction review are weak. | M-OPS-LOGGING-01. |
| 10 | Data integrity/truthful missing data | READY | Live DB integrity `ok`, zero FK violations, catalog audit `ok`; API/UI tests distinguish not-imported coverage and only BSEU live monitoring. | No blocking gap. Data coverage is intentionally partial: 47 universities but only 1 imported Program/Offering. | None; preserve constraints. |
| 11 | Deployment and rollback | PARTIAL | Install/update/rollback/healthcheck scripts and paired DB backup behavior are documented. | Code rollback does not restore SQLite and scripts have not been run together against a production-like host/copy. | M-PROD-REHEARSAL-01. |
| 12 | Operator documentation | PARTIAL | README covers install, update, rollback, logs, backup, restore, XML changes and API. | No single executed go/no-go checklist records host values, backup ID, revision, health results, rollback trigger and restore proof. | M-PROD-REHEARSAL-01. |
| 13 | Repository cleanliness/artifacts | READY | Initial tree was clean; `.gitignore` excludes env/SQLite/runtime/logs/build dependencies; final verification is restricted to two docs. | No blocking gap. | None. |
| 14 | Browser principal routes | READY | Five real routes at 360/768/1280 produced expected H1/title, no alert, no horizontal overflow and no console warning/error; all required GETs returned 200. | Browser screenshot capture timed out, so no screenshot artifact was retained; DOM, viewport and console evidence was still executed. | None for contract readiness; repeat screenshots during production-like rehearsal if an artifact is required. |

## 6. Executed commands and results

| Command/check | Result |
|---|---|
| `Test-Path '<requested repository>'` | PASS; path exists. |
| `git rev-parse --show-toplevel` | PASS; requested Git root confirmed. |
| `git status --short` | PASS; initial tree clean. Before commit, only the two authorized documentation files are changed. |
| `git branch --show-current` | PASS; `feature/platform-redesign`. |
| `git log -4 --oneline` | PASS; audited HEAD `b41ec14 feat: add program detail page`. |
| `./check.ps1` (PowerShell invocation `\.\check.ps1`) | PASS: 105 passed/1 deselected ordinary backend; 1 live passed; Ruff passed; 4 frontend test files/49 tests passed; lint/typecheck/build passed. |
| `python -m alembic current`, `heads`, `history --verbose` from `backend` | PASS; one head/current revision `0003_backfill_bseu_catalog`. |
| `python -m app.cli audit-catalog` | PASS; `status=ok`, 47 universities, 1 Program, 1 Offering, explicit missing-coverage warnings. |
| Tracked-file credential-literal scan | PASS after review: two matches were test-only assignments in `test_scraper_304.py`; no production credential literal or private key found. |
| `bash -n deploy/*.sh` / `shellcheck` discovery | NOT EXECUTED: neither `bash` nor `shellcheck` is installed in this Windows environment. Recorded as production-rehearsal gap. |
| `./start-dev.ps1` | PASS; exactly one backend command and one frontend command recorded by the PID files. |
| Required UI/API GET smoke | PASS; `/`, `/universities`, real BSEU University, real Economic Informatics Program, `/monitor`, catalog meta/list/health and both detail APIs returned 200. |
| `/api/health` in safe mode | PASS; `scheduler_running=false`, `refresh_in_progress=false`, `last_error=null`. |
| Browser route grid | PASS; 5 routes × 3 widths, correct rendered H1/title, no alerts/overflow. |
| Browser console | PASS; zero warning/error entries. |
| Browser screenshot artifact | LIMITED; full-page, viewport and clipped captures timed out in the browser backend. No application failure or console error accompanied the timeout. |
| `./stop-dev.ps1` | PASS; backend and frontend stopped; ports 8000/5173 no longer listening. |
| SQLite post-smoke read-only inspection | PASS; counts/IDs/timestamps unchanged; integrity `ok`; zero FK violations. |
| `git diff --check` | PASS after documentation changes. |

No request was sent to `POST /api/refresh`. The development server was not run
concurrently with tests. Network-writing catalog commands, migrations, seed/import,
Telegram delivery and production deployment were not invoked.

## 7. Database side-effect proof

The database was opened through a read-only immutable SQLite URI for both
measurements.

| Table/value | Before start | After stop | Result |
|---|---:|---:|---|
| `admission_snapshots` count / max ID | 8 / 8 | 8 / 8 | unchanged |
| latest snapshot `fetched_at` | `2026-07-15 12:09:16.654270` | same | unchanged |
| `scraper_runs` count / max ID | 91 / 91 | 91 / 91 | unchanged |
| latest run `started_at` | `2026-07-15 12:09:15.512880` | same | unchanged |
| latest run `finished_at` | `2026-07-15 12:09:16.655609` | same | unchanged |
| `notification_logs` count / max ID | 0 / null | 0 / null | unchanged |
| latest notification `sent_at` | null | null | unchanged |
| Universities / Programs / Offerings | 47 / 1 / 1 | 47 / 1 / 1 | unchanged |
| Alembic revision | `0003_backfill_bseu_catalog` | same | unchanged |
| `PRAGMA integrity_check` | `ok` | `ok` | PASS |
| `PRAGMA foreign_key_check` violations | 0 | 0 | PASS |

This proves the runtime smoke did not create Snapshot, ScraperRun or Notification
records and did not mutate catalog coverage.

## 8. Prioritized gap register

No P0 gap was found. The current data remained intact, secret-literal scanning did
not find a production credential, and safe-mode runtime created no records.

### GAP-01 — P1 — BSEU adapter/registry prerequisite missing

- **Affected:** `backend/app/scraper.py`, `backend/app/main.py`, missing
  `backend/app/adapters/` and registry/monitoring-service boundary.
- **Evidence:** production refresh directly calls `AdmissionScraper.refresh`; native
  file discovery and graph search found no adapter registry. Roadmap M9 depends on M4.
- **Required outcome:** production BSEU monitoring resolves through the documented
  registry-backed adapter/service while preserving parser, 304, snapshots,
  scheduler, manual refresh, Telegram and legacy API behavior.
- **Non-goals:** another university adapter, removal of legacy endpoints/tables,
  catalog UI changes, recommendations.
- **Verification:** registry duplicate/unknown tests plus existing parser/live/HTTP/
  304/dedup/scheduler/manual-refresh/Telegram parity and full `check.ps1`.

### GAP-02 — P1 — Recommendations prerequisite missing

- **Affected:** absent recommendation API/service/schemas/tests and canonical subject
  coverage.
- **Evidence:** no implementation symbols/routes; live catalog has only one Program
  and Offering and no adequate subject dataset.
- **Required outcome:** M7's deterministic, explainable, source-backed contract after
  adequate offering/subject data exists.
- **Non-goals:** ML, admission probability, fabricated catalog completion or UI.
- **Verification:** deterministic fixtures, strict unknown/stale handling,
  boundary/performance tests and full suite.

### GAP-03 — P1 — Anonymous profiles/favorites prerequisite missing

- **Affected:** absent profile/favorite/compare models, cookie security and APIs.
- **Evidence:** no relevant implementation; roadmap M8 is a transitive dependency of M9.
- **Required outcome:** isolated anonymous ownership with signed HttpOnly cookie and
  idempotent local-state merge.
- **Non-goals:** email/password authentication, Telegram linking, watchlists.
- **Verification:** cookie/security, authorization isolation, cascade and merge tests.

### GAP-04 — P1 — Watchlists/per-profile Telegram prerequisite missing

- **Affected:** absent link-token, account, watchlist and delivery ownership layers;
  current `backend/app/telegram.py` is owner-only.
- **Evidence:** no watchlist/linking implementation; M9 is a direct M13 dependency.
- **Required outcome:** attributable per-profile delivery with one-use hashed linking,
  retry/dedup and legacy owner parity.
- **Non-goals:** replacing the owner chat ID, broad bot UI or other channels.
- **Verification:** expiry/one-use/no-raw-token, isolation, duplicate/retry/recovery and
  owner-compatibility tests.

### GAP-05 — P1 — Production-like backup/migration/rollback rehearsal absent

- **Affected:** `deploy/install-server.sh`, `update-server.sh`,
  `rollback-server.sh`, README recovery procedures and Alembic path.
- **Evidence:** scripts and unit/integration migration tests exist, but no executed
  Ubuntu copy rehearsal or restore evidence exists; Windows lacks bash/shellcheck.
- **Required outcome:** timestamped evidence for backup, integrity/FK, upgrade,
  health, code rollback, paired DB restore and service recovery on a disposable
  production-like copy.
- **Non-goals:** production deployment, destructive migration F, infrastructure replacement.
- **Verification:** scripted rehearsal with before/after hashes/counts/revision,
  Nginx/systemd health, rollback/restore and documented go/no-go.

### GAP-06 — P1 — Resource and deployment budgets unverified

- **Affected:** catalog queries, one-worker scheduler, systemd memory/disk limits,
  Nginx/base path/TLS and healthcheck.
- **Evidence:** query-count unit ceilings and configuration templates exist, but no
  memory/disk/load measurements or executed Linux one-worker/TLS/base-path check.
- **Required outcome:** measured budgets on VPS-like resources and a passing dedicated
  host/base-path/TLS/systemd healthcheck.
- **Non-goals:** Redis/PostgreSQL, multiple workers, infrastructure replacement.
- **Verification:** recorded request/load sample, peak RSS, DB/disk growth, query
  counts, scheduler job cardinality and external HTTPS health/navigation.

### GAP-07 — P1 — Public error surface can expose internal/upstream text

- **Label:** **AUDITOR-ADDED SAFETY REQUIREMENT**
- **Justification:** necessary to prevent security/operational detail exposure;
  `backend/app/main.py` returns stored `ScraperRun.error_message` through public
  `/api/health` and `/api/status`, while manual refresh already uses a sanitized
  public error.
- **Required outcome:** public endpoints return stable sanitized categories/messages;
  full detail remains only in protected logs with no secrets.
- **Non-goals:** changing success payloads, hiding failure state, redesigning health.
- **Verification:** tests seed sensitive-looking upstream/internal text and assert it
  is absent from every public response but present in captured protected logs.

### GAP-08 — P2 — Operational log correlation is limited

- **Affected:** `backend/app/main.py` logging configuration and operator diagnostics.
- **Evidence:** plain `logging.basicConfig`; no request/run correlation identifier or
  documented structured redaction policy.
- **Required outcome:** bounded structured fields or consistent correlation context
  for request, scheduler run and notification without logging secrets.
- **Non-goals:** external log stack, tracing platform or infrastructure replacement.
- **Verification:** capture tests for correlation/redaction and operator example logs.

### GAP-09 — P2 — Non-blocking build/deprecation warnings

- **Affected:** frontend bundle composition and SQLAlchemy SQLite datetime defaults.
- **Evidence:** Vite reports a chunk above 500 kB; backend tests report SQLAlchemy
  datetime deprecation warnings. Both builds/tests pass.
- **Required outcome:** either remove warnings through narrow supported changes or
  document accepted budgets before the relevant dependency upgrade.
- **Non-goals:** frontend redesign, database replacement, speculative refactor.
- **Verification:** warning-free focused build/tests or an explicit reviewed budget.

## 9. Selected next implementation milestone

### M-BSEU-ADAPTER-01 — Registry-backed BSEU monitoring with parity

This is the exact next milestone. It resolves GAP-01 and implements roadmap section
4 only.

Selection rationale:

1. no unresolved P0 exists;
2. M4 is the earliest and highest-impact missing P1 roadmap prerequisite because it
   owns the production-critical BSEU cutover and directly unlocks M9;
3. it is a coherent boundary change with explicit parity tests, not a bundle of
   unrelated production-hardening repairs;
4. beginning section 13 first would contradict its own dependency gate and would
   harden an incomplete first release.

Completion must mean the current production BSEU flow delegates through the
documented adapter registry/service with no API, snapshot, 304, scheduler,
calculation, Telegram or live-test regression. Stop after that one milestone;
do not include profiles, watchlists, recommendations or production rehearsal.

## 10. Explicitly deferred work

- M7 Recommendations API and the source-backed subject/program coverage it needs;
- M8 anonymous profiles, favorites and compare;
- M9 watchlists and per-profile Telegram linking;
- section 13 production-like backup/restore/migration/rollback rehearsal;
- measured memory/disk/load/query budgets and Linux one-worker scheduler proof;
- Nginx/TLS/base-path deployment validation on the intended host;
- sanitized public error surface and logging improvements;
- destructive migration F, any new university adapter, infrastructure replacement,
  production deployment and push.

## 11. Audit conclusion

The repository has a healthy, side-effect-free development runtime and a verified
read-only public catalog/detail vertical slice. Legacy BSEU behavior, current schema,
catalog truthfulness and browser layout checks pass. That is not equivalent to final
integration readiness: four roadmap prerequisites are absent and the production
rehearsal/resource/operations evidence has not been executed.

**Go/no-go for beginning roadmap section 13: NO-GO.** Complete
`M-BSEU-ADAPTER-01` next, then continue the remaining prerequisite chain before a
new section 13 readiness decision.
