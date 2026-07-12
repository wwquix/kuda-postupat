# Platform redesign baseline

## Timestamp and environment

- Date and time: 2026-07-12 20:45:21 +03:00 (Europe/Minsk)
- OS: Microsoft Windows NT 10.0.26220.0 (Windows 11)
- PowerShell version: 7.5.8
- Python version: 3.13.14 (`.venv\Scripts\python.exe`)
- Node.js version: v26.4.0
- npm version: 11.17.0

## Repository state

- Repository root reported by Git: `C:\Users\Yura`
- Project root: `C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor`
- Active branch: `master`
- Latest commit: none; `git log -1 --oneline` fails because the branch has no commits
- Working tree state: not clean. The project is inside a Git worktree rooted at the user profile and is untracked as part of that wider worktree. Git also reports many unrelated untracked files under `C:\Users\Yura`.
- No tracked paths matching `.env`, SQLite databases, `.venv`, `node_modules`, or `.runtime` were found by `git ls-files`.
- Ignore checks passed for `.env`, `backend/data/admission.db`, `.venv`, and `frontend/node_modules`.
- `backups/*.db` is not ignored by the current Git rules.
- No commit, push, checkout, or branch creation was performed.

## Project structure

- Backend path: `backend`
- Backend entrypoint: `backend/app/main.py`; development command from `start-dev.ps1`: `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, working directory `backend`
- Frontend path: `frontend`
- Frontend development command from `start-dev.ps1`: `npm.cmd run dev -- --host 127.0.0.1 --port 5173`, working directory `frontend`
- Database path: `backend/data/admission.db` (resolved from `DATABASE_URL=sqlite:///./data/admission.db` with backend as working directory)
- Environment path: `.env`
- Python dependency files: `backend/requirements.txt`, `backend/requirements-dev.txt`; tool configuration: `backend/pyproject.toml`
- Frontend package file: `frontend/package.json`; lock file: `frontend/package-lock.json`
- Backend tests: `backend/tests`; live test: `backend/tests/test_live.py`; fixtures: `backend/tests/fixtures`
- Production build command: `npm.cmd run build`, working directory `frontend`
- PowerShell scripts checked: `setup.ps1`, `start-dev.ps1`, `stop-dev.ps1`, `refresh.ps1`, `check.ps1`. All five parse with zero PowerShell syntax errors and all five are UTF-8 with BOM.

## Verification commands

| Check | Working directory | Command | Exit code | Result |
|---|---|---|---:|---|
| Git status | project root | `git status --short` | 0 | Worktree is not clean; project is within a broader untracked user-profile worktree. |
| Git branch | project root | `git branch --show-current` | 0 | `master` |
| Git root | project root | `git rev-parse --show-toplevel` | 0 | `C:/Users/Yura` |
| Latest commit | project root | `git log -1 --oneline` | 128 | No commits exist on `master`. |
| Full verification | project root | `.\check.ps1` | 0 | All checks completed. |
| Ordinary pytest | `backend` | `..\.venv\Scripts\python.exe -m pytest` | 0 | 25 passed, 0 failed, 1 deselected (live). |
| BSEU live pytest | `backend` | `..\.venv\Scripts\python.exe -m pytest -m live -o addopts=` | 0 | 1 passed, 0 failed, 25 deselected. |
| Ruff | `backend` | `..\.venv\Scripts\python.exe -m ruff check .` | 0 | All checks passed. |
| ESLint | `frontend` | `npm.cmd run lint` | 0 | Passed. |
| TypeScript | `frontend` | `npm.cmd run typecheck` | 0 | Passed (`tsc -b --pretty false`). |
| Vite production build | `frontend` | `npm.cmd run build` | 0 | Built successfully; 2,336 modules transformed. Vite warned that the 592.62 kB JS chunk exceeds 500 kB. |
| First development start | project root | `.\start-dev.ps1` | 0 | Backend HTTP 200 on port 8000; frontend HTTP 200 on port 5173. |
| Repeated development start | project root | `.\start-dev.ps1` | 0 | PID values stayed `22116` and `18496`; script reported that no repeated processes were created. |
| Health endpoint | project root | `GET http://127.0.0.1:8000/api/health` | 0 | HTTP 200; `status=ok`, `database=ok`, scheduler running. |
| Status endpoint | project root | `GET http://127.0.0.1:8000/api/status` | 0 | HTTP 200; returned state, last run, consecutive errors, and next run time. |
| Config endpoint | project root | `GET http://127.0.0.1:8000/api/config` | 0 | HTTP 200; public configuration only. |
| Specialties endpoint | project root | `GET http://127.0.0.1:8000/api/specialties` | 0 | HTTP 200; one specialty returned. |
| Latest endpoint | project root | `GET http://127.0.0.1:8000/api/specialties/1/latest` | 0 | HTTP 200; current snapshot and freshness fields returned. |
| History endpoint | project root | `GET http://127.0.0.1:8000/api/specialties/1/history` | 0 | HTTP 200; two snapshots returned. |
| Score distribution endpoint | project root | `GET http://127.0.0.1:8000/api/specialties/1/score-distribution` | 0 | HTTP 200; 67 ranges returned, count sum 11. |
| Manual live refresh | project root | `.\refresh.ps1` | 1 | Backend returned HTTP 502 because an upstream HTTP 304 was incorrectly raised as `HTTPStatusError`. |
| Repeated manual refresh | project root | `.\refresh.ps1` | 1 | Same 304-to-502 defect; no snapshot was added. |
| Stop development processes | project root | `.\stop-dev.ps1` | 0 | Only verified project trees were stopped; both PID files removed, ports 8000/5173 no longer listening. |

All API responses above were scanned for secret field names or bearer/token material. No `MANUAL_REFRESH_TOKEN`, `TELEGRAM_BOT_TOKEN`, session secret, password, SSH data, or refresh authorization value was exposed.

## Current BSEU live data

- Source URL: `https://bseu.by/abiturient/xml/1.xml`
- Successful new source request: started 2026-07-12 20:38:39 +03:00, finished 2026-07-12 20:38:41 +03:00 (about 1.52 seconds), HTTP 200
- Rows found in the source: 77
- Target specialty found: yes
- Source updated at: 2026-07-12 15:00:00 +03:00
- Specialty: Экономическая информатика
- Study form: дневная
- Funding type: платная
- Places: 60
- Applications: 11
- Distribution total: 11
- Distribution ranges: 67
- Competition: 0.18 applications per place
- Estimated cutoff: not calculated because applications (11) do not exceed places (60)
- User score: 276
- Estimated position: 5
- User status: Уверенно проходит
- Freshness status: stale (`is_stale=true`); the live request succeeded, but the source's own update timestamp was older than the configured 30-minute threshold
- The live pytest independently passed against the official BSEU source before the local service run.
- The later explicit manual request reached the same official URL and received HTTP 304 Not Modified, but the application mishandled that valid response and returned HTTP 502. This is a local code defect, not evidence that the official source was unavailable.

## Database inventory

- SQLite file size after a read connection checkpointed the WAL: 61,440 bytes
- User tables: 5
- Universities: no `universities` table exists in the current pre-redesign schema
- Specialties/programs: 1 row in `specialties`; no separate `programs` table exists
- Admission snapshots: 2
- Scraper runs: 26
- Notification events: 0 rows in `notification_logs`
- Alembic/schema revision: no Alembic configuration or revision files exist; no revision is recorded

| Table | Row count |
|---|---:|
| `admission_snapshots` | 2 |
| `http_cache_state` | 1 |
| `notification_logs` | 0 |
| `scraper_runs` | 26 |
| `specialties` | 1 |

## Deduplication check

- Snapshot count before the successful startup refresh: 2
- Snapshot count after the successful startup refresh: 2
- Snapshot count before the repeated explicit refresh: 2
- Snapshot count after the repeated explicit refresh: 2
- Latest snapshot time before and after: 2026-07-12 12:13:54.573894 UTC
- Raw data hash before and after: `f80613b949ae2480b79cb375a9463efe11ea28e43ac015a912968b1a8a77e5f1`
- Result: hash deduplication passed on the fresh HTTP 200 startup refresh (`rows_found=77`, no new snapshot). The subsequent explicit refreshes also created no duplicate, but they failed before normal deduplication handling because HTTP 304 was converted into an error.

## Backup

- Source database: `C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor\backend\data\admission.db`
- Backup path: `C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor\backups\admission-before-platform-redesign-20260712-204521.db`
- File size: 61,440 bytes
- SHA-256: `fa2bf292f29e701b434d2de3ea4c3332b2284e4dad1261786e94c6b953d07a98`
- Verification result: source and backup both returned `ok` from `PRAGMA integrity_check`; all five user-table names match; row counts match for every table.
- Backup timing: created only after `stop-dev.ps1` completed and ports 8000/5173, PID files, and project service processes were confirmed absent.
- Git ignore result: the backup is currently not ignored because no rule covers `backups/*.db`.

## Known issues

1. **Resolved during baseline stabilization:** manual conditional refresh was broken for an unchanged upstream document. `AdmissionScraper._fetch()` called `response.raise_for_status()` on HTTP 304 before `refresh()` could execute its `status_code == 304` branch. The three retries received 304, the run was stored as `error`, and `/api/refresh` returned 502 instead of `not_modified`.
2. **Resolved during baseline stabilization:** the project directory was not its own usable committed Git repository. Git resolved the root to `C:\Users\Yura`; branch `master` had no commits; the project and many unrelated user-profile paths were untracked. This prevented a meaningful project-only working-tree baseline and `git diff --stat`.
3. **Resolved during baseline stabilization:** `backups/*.db` was not ignored by Git. The milestone backup therefore appeared inside the already-untracked project tree and could have been accidentally added.
4. Current official source data is stale according to the configured 30-minute threshold (source timestamp 15:00 +03:00 at a 20:38 +03:00 check). The HTTP 200 response and passing live test show that the source was reachable; staleness concerns the publisher timestamp, not request availability.
5. Vite production build succeeds but warns that the generated 592.62 kB JavaScript chunk is larger than 500 kB.

## Baseline stabilization

- Stabilized at: 2026-07-12 21:00:25 +03:00 (Europe/Minsk)
- HTTP 304 handling: `_fetch()` now returns 304 to the refresh flow instead of raising it as an HTTP error. With an existing snapshot, the run is committed as `not_modified`, cache `checked_at` is updated, and no body is parsed. Without any snapshot, the scraper performs exactly one request without `If-None-Match` or `If-Modified-Since`; a subsequent 200 follows the normal parser/snapshot path, while a second 304 produces a controlled sanitised API error.
- Manual refresh result: `.\refresh.ps1` completed successfully and reported `HTTP=200`, `status=not_modified`, zero created snapshots, and the message `Источник доступен, данные не изменились`. The official source response recorded in the scraper run was HTTP 304.
- Snapshot count before and after: 2 → 2.
- Raw data hash before and after: `f80613b949ae2480b79cb375a9463efe11ea28e43ac015a912968b1a8a77e5f1`.
- Scraper run: `not_modified`, upstream HTTP 304, zero rows parsed, zero consecutive errors. Total scraper runs after live verification: 28.
- Freshness behavior: `last_checked_at` advanced to 2026-07-12 18:00:25 UTC; `source_updated_at` remained 2026-07-12 15:00:00 +03:00; `is_stale` remained `true` because official source age is independent of successful HTTP availability checks.
- Telegram behavior: notification count remained 0. No change, failure, or recovery notification was sent for either real 304 check.
- Regression tests: 6 dedicated HTTP 304 tests passed, covering cached success, manual endpoint HTTP 200, one unconditional recovery request, controlled repeated 304 without data, freshness semantics, and notification silence.
- Full verification: 31 ordinary tests passed (1 live deselected); the separate BSEU live test passed (1 passed, 31 deselected); Ruff, ESLint, TypeScript, and Vite production build passed. Vite retained the existing non-failing chunk-size warning.
- PowerShell compatibility: the modified `refresh.ps1` has zero parser errors and remains UTF-8 with BOM.
- Project Git root: `C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor`.
- Branch: `feature/platform-redesign`.
- Initial commit: this project checkpoint, with message `fix: establish project baseline and handle HTTP 304`.
- Git ignore verification: `.env`, `backend/data/admission.db`, the baseline backup, `frontend/node_modules`, and `.venv` are ignored; `.env.example` remains intentionally trackable.
- Secret audit result: 64 tracked candidates inspected; zero runtime/SQLite/backup/dependency candidates, zero matches for actual local secret values, zero private keys, and zero Telegram bot token patterns. Template placeholders and runtime-generated values in `.env.example` and deployment scripts are not real secrets.
- Parent Git repository: `C:\Users\Yura\.git` was not removed, modified, or reconfigured.

## Baseline conclusion

**Ready for redesign.** The core BSEU parser, calculations, ordinary tests, live test, linters, type checking, production build, local backend/frontend startup, API reads, scheduler startup, SQLite persistence, hash-based snapshot deduplication, HTTP 304 path, manual refresh, freshness semantics, Telegram silence for unchanged data, project-scoped Git repository, safe ignore rules, and secret audit are verified. The stale official publisher timestamp and Vite chunk warning remain visible as non-blocking operational observations. No blocker remains before Milestone 1.
