# Alembic bootstrap and core catalog schema result

Migration A+B executed on the local SQLite database on 13 July 2026 (Europe/Minsk). The application was stopped, the strict legacy fingerprint and canonical backup were verified, and no downgrade was run against the main database.

## Revisions and timing

| Step | Result | Wall time |
|---|---|---:|
| Pre-migration revision | unversioned exact legacy schema | — |
| `stamp 0001_legacy_baseline` | `0001_legacy_baseline` | 970 ms |
| `upgrade head` | `0002_core_catalog_schema` | 1,017 ms |
| `alembic heads` | one head: `0002_core_catalog_schema` | — |
| `alembic check` | no new upgrade operations detected | — |

Baseline downgrade is deliberately a no-op for legacy tables. Catalog downgrade was exercised only on isolated temporary databases; it removes only empty catalog tables and refuses a non-empty catalog schema.

## Recovery artifact

- Canonical backup: `backups/admission-before-alembic-20260713-102427.db`.
- Backup SHA-256: `a772f8982e28cfeacb7726844118b0121b4d43916014e4e7720bc7fa5d0185f3`.
- Backup size: 77,824 bytes.
- Restore verification: PASS; temporary restore file removed.
- Full details and the recovered pre-migration CLI routing artifacts: [alembic-preflight.md](alembic-preflight.md).

## Immediate pre/post migration reconciliation

This comparison was taken immediately after `upgrade head` and before application startup or live refresh, so it isolates migration effects from expected runtime audit writes.

| Legacy table | Before | Immediately after |
|---|---:|---:|
| `specialties` | 1 | 1 |
| `admission_snapshots` | 2 | 2 |
| `scraper_runs` | 31 | 31 |
| `notification_logs` | 0 | 0 |
| `http_cache_state` | 1 | 1 |

Exact all-row and legacy `sqlite_master` comparisons passed. Legacy IDs, snapshot `raw_data_hash`, distribution JSON, `fetched_at`, `source_updated_at`, scraper-run fields and cache validators/timestamps were unchanged by stamp/upgrade.

Post-migration database checks:

- `PRAGMA integrity_check`: `ok`;
- `PRAGMA foreign_key_check`: 0 violations;
- runtime Alembic schema guard: PASS;
- immediate post-migration file size: 212,992 bytes;
- immediate post-migration SHA-256: `4203d94c3596872bd332e5528873fbc64ca02bc115922b616f804f0120acf25c`.

## Catalog schema created

| New table | Rows after migration |
|---|---:|
| `universities` | 0 |
| `university_categories` | 0 |
| `university_category_links` | 0 |
| `programs` | 0 |
| `program_offerings` | 0 |
| `data_sources` | 0 |

The corresponding ORM models are `University`, `UniversityCategory`, `UniversityCategoryLink`, `Program`, `ProgramOffering` and `DataSource`. Stable persisted enum values, uniqueness, non-blank/range checks, minimal indexes and explicit FK delete behavior are enforced by the revision and ORM metadata.

Intentionally not created or changed:

- no BSEU university/program/offering rows and no 47-university import;
- no seed command;
- no `legacy_specialty_mappings` table or mapping rows;
- no `program_offering_id` on `admission_snapshots`;
- no alias, subject, profession, finance, dormitory, media or user tables;
- no scraper/cache/Telegram backfill;
- no catalog/search API and no frontend changes.

## Admission year evidence

The next BSEU backfill may use explicit reviewed parameter `2026`: the official 2026 admission-plan PDF and current official XML agree on «Экономическая информатика», full-time paid plan 60. The landing page alone is stale and is not used to infer the year. Full evidence: [admission-year-evidence.md](admission-year-evidence.md).

## Verification

- Migration/config tests: 17 passed in the focused pre-migration gate; final suite includes all migration cases.
- Fresh upgrade, existing legacy verify/stamp/upgrade, empty catalog downgrade, re-upgrade, baseline no-op, non-empty downgrade refusal, constraints, cascades and production-path `create_all` guard: PASS on disposable databases.
- Full `check.ps1`: 43 ordinary backend tests passed; live BSEU test passed; Ruff, ESLint, TypeScript and Vite production build passed.
- Legacy API runtime: health, config, status, specialties, latest snapshot, history and score distribution returned HTTP 200.
- Startup conditional request: HTTP 304 / `not_modified`; snapshots stayed at 2 and notifications at 0.
- Manual refresh after the five-minute limiter window: HTTP 200 application response, upstream HTTP 304, `status=not_modified`, 0 snapshots created.

## Runtime checkpoint

Application startup and manual refresh legitimately append `scraper_runs` audit rows and update HTTP cache check time. These are runtime verification effects, not migration effects.

- Startup run: `not_modified`, HTTP 304; `scraper_runs` 31 → 32.
- Manual `refresh.ps1` run after the limiter window: HTTP 200 API response, `not_modified`, upstream HTTP 304; `scraper_runs` 32 → 33.
- Final snapshots: 2; no duplicate snapshot created.
- Final notification rows: 0; Telegram did not send or enqueue a duplicate notification.
- Backend/frontend were stopped; PID files were removed and ports 8000/5173 had zero listeners.

## Known limitations / next milestone blockers

There is no blocker to starting the separately reviewed BSEU canonical identity/backfill milestone: the year evidence, backup, baseline and catalog foundation are ready. That next milestone must still take a new backup, accept `2026` explicitly, create the mapping contract and reconcile every legacy value again. It must not infer a year, overwrite snapshots, or combine the backfill with adapter/API/frontend work.
