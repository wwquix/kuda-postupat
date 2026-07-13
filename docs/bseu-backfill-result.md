# BSEU catalog backfill result

Milestone completed locally on 13 July 2026 (Europe/Minsk). The main database was upgraded while the application was stopped. Downgrade was exercised only on disposable copies. No other university was imported.

## Recovery artifact and revisions

- Backup: `backups/admission-before-bseu-backfill-20260713-202551.db`.
- Backup SHA-256: `54e72c0ed298f39c3d68b7d38efb7d0875b1f75638b8a30405ea3b208f7d128a`.
- Backup size: 225,280 bytes.
- Backup validation: `PRAGMA integrity_check = ok`, zero foreign-key violations, exact logical match with the source database.
- Revision before: `0002_core_catalog_schema`.
- Revision after: `0003_backfill_bseu_catalog`.
- Final Alembic state: one head, `alembic check` reports no new upgrade operations.

The main database was never downgraded.

## Mapping strategy

The backfill uses both accepted additive links:

1. `legacy_specialty_mappings` stores the explicit identity mapping from legacy specialty ID 1 to program ID 1 and program offering ID 1.
2. Nullable `admission_snapshots.program_offering_id` and `scraper_runs.data_source_id` provide direct catalog links for efficient reads and future adapter cutover.

Legacy foreign keys, row identities and writer behavior remain in place. The migration adds catalog links without replacing the legacy specialty relation or making the new columns mandatory.

## Created canonical records

| Record | ID | Stable identity |
|---|---:|---|
| University | 1 | `code=bseu`, `slug=bseu` |
| University category | 1 | `code=economic` |
| University/category link | — | university 1 / category 1 |
| Program | 1 | `code=6-05-0311-05`, `slug=economic-informatics` |
| Program offering | 1 | 2026, `full_time`, `paid`, 60 places |
| Data source | 1 | official admission XML, `admission_xml` |
| Legacy mapping | 1 | mapping key is `legacy_specialty_id=1` |

The frozen canonical values are backed by the official BSEU program catalog, 2026 admission-plan PDF and XML endpoint recorded in the source fields. The migration itself performs no network requests.

## Row reconciliation

The immediate post-migration comparison was performed before application startup, so it isolates migration effects from later runtime audit writes.

| Table | Before | Immediately after migration | Final after runtime smoke |
|---|---:|---:|---:|
| `specialties` | 1 | 1 | 1 |
| `admission_snapshots` | 4 | 4 | 5 |
| `scraper_runs` | 62 | 62 | 64 |
| `notification_logs` | 0 | 0 | 0 |
| `http_cache_state` | 1 | 1 | 1 |
| `universities` | 0 | 1 | 1 |
| `university_categories` | 0 | 1 | 1 |
| `university_category_links` | 0 | 1 | 1 |
| `programs` | 0 | 1 | 1 |
| `program_offerings` | 0 | 1 | 1 |
| `data_sources` | 0 | 1 | 1 |
| `legacy_specialty_mappings` | absent | 1 | 1 |

Immediately after migration all four existing snapshots and all 62 existing scraper runs were linked. At the final checkpoint all five snapshots point to offering 1 and all 64 runs point to data source 1. Database integrity is `ok` with zero foreign-key violations.

## Snapshot identity, hashes, JSON and timestamps

All original snapshot fields were compared against the backup immediately after upgrade. IDs, specialty IDs, admission values, `raw_data_hash`, `distribution_json`, `fetched_at` and `source_updated_at` were byte-for-byte/logically unchanged. Only the newly introduced nullable catalog link was populated.

| Snapshot ID | `fetched_at` before/after | `source_updated_at` before/after | `raw_data_hash` before/after |
|---:|---|---|---|
| 1 | `2026-07-12 10:57:50.420875` | `2026-07-12 12:00:00.000000` | `c32bf82f426b744e8da6f03aa92e8cf1e59c17ce68097f20e04f2b039634fd95` |
| 2 | `2026-07-12 12:13:54.573894` | `2026-07-12 15:00:00.000000` | `f80613b949ae2480b79cb375a9463efe11ea28e43ac015a912968b1a8a77e5f1` |
| 3 | `2026-07-13 09:49:34.890313` | `2026-07-13 12:00:00.000000` | `3b6077bffe7eef11b373b166247a17d28aba908f6c65af7713fe7fdd7ca92810` |
| 4 | `2026-07-13 12:09:34.510968` | `2026-07-13 15:00:00.000000` | `2cd36ba0a73f8ed76b44057ab097caaeb2d80dc7825a86d2b04a1222437defc0` |

The startup live refresh observed a new official source version and legitimately created snapshot ID 5 with hash `3f7235e81a8cb40f6f459a3283a9092293e5261977fd7c93637c2fd1204c8669`. The later manual refresh received the same content and did not create a duplicate: snapshot count stayed 5 and the latest hash stayed unchanged.

## Idempotency and fresh-database behavior

- Re-running the backfill helper produces no duplicate university, category, program, offering, data source or mapping rows.
- Unique constraints reject duplicate BSEU code/slug and duplicate offering identity.
- A fresh empty database upgrades through `0003`; it contains the canonical catalog seed and no fabricated history.
- The first successful refresh on a fresh database creates the legacy specialty, mapping, linked snapshot and linked scraper run.

These cases are covered by disposable-database migration and operational tests.

## Catalog API checks

The following generic read-only endpoints were added and returned HTTP 200 for the canonical BSEU records:

- `GET /api/universities/{slug}`;
- `GET /api/universities/{slug}/programs`;
- `GET /api/program-offerings/{id}`;
- `GET /api/program-offerings/{id}/latest`;
- `GET /api/program-offerings/{id}/history`;
- `GET /api/program-offerings/{id}/score-distribution`.

The offering latest/history/distribution endpoints resolve the preserved legacy snapshot data through the catalog mapping. Routes use repository/service queries and Pydantic response schemas; the generic API router contains no university-slug branch.

All seven legacy BSEU GET endpoints also returned HTTP 200 with compatible response shapes. The existing React dashboard rendered the configured specialty, plan 60, 25 applications and five history points without a visible error, horizontal overflow or browser-console warnings/errors.

## Scraper and live verification

- Startup refresh: upstream HTTP 200, `status=success`, 77 rows, one new snapshot (ID 5), linked to offering 1; one linked scraper run was appended.
- Manual `refresh.ps1` after the rate-limit window: API HTTP 200, upstream HTTP 200, `status=success`, 77 rows, zero snapshots created; a linked scraper run was appended.
- Snapshot deduplication: PASS; count stayed 5 during the manual refresh and the latest hash did not change.
- Notification safety: `notification_logs` stayed at 0; no duplicate Telegram event was sent or enqueued.
- Conditional HTTP 304 behavior: the official server returned HTTP 200 during this live window, so no false live-304 claim is made. The unchanged 304 path, cache validators and no-snapshot/no-notification behavior pass the dedicated six-test scraper 304 suite.
- Final source mirror: healthy, zero consecutive failures, no last error, linked data source ID 1.

The legacy state remains authoritative during this milestone; `DataSource` receives an additive runtime-health mirror so the old monitor and the new catalog view remain consistent until a separately approved adapter cutover.

## Downgrade verification

The `0003` downgrade was tested only on a temporary database. It removed the exact migration-owned BSEU seed, mapping table and new nullable link columns, while preserving the complete legacy specialty, snapshots, scraper runs and notification history. Legacy API checks passed after downgrade to `0002_core_catalog_schema`; integrity and foreign-key checks remained clean.

The downgrade is guarded: it refuses to delete catalog data when seeded identities were manually changed or acquired new dependencies.

## Verification summary

- Focused migration, backfill, catalog API, compatibility and scraper suite: 23 passed.
- Full ordinary backend suite: 50 passed, 1 deselected; only Python 3.13 SQLite datetime deprecation warnings.
- Live BSEU integration: 1 passed, 50 deselected.
- Ruff: passed.
- ESLint: passed.
- TypeScript `tsc --noEmit`: passed.
- Vite production build: passed.
- `alembic check`, single-head check, CLI backfill verification, SQLite integrity and foreign-key checks: passed.
- Runtime legacy API, new catalog API and real-browser dashboard smoke: passed.

## Known limitations and stop boundary

- `DataSource` mirrors legacy scraper runtime state; changing the writer to a catalog adapter is a future milestone.
- The current official server returned HTTP 200 rather than 304 during live verification; the 304 contract is covered by automated tests.
- Vite reports the existing warning that the main bundle exceeds 500 kB; the build succeeds and frontend code was not changed.
- The six catalog routes are the explicit scope exception requested for this milestone; no search, new frontend, common seed or adapter extraction was started.
- Importing the remaining 46 universities still requires its own audited source/import milestone. This milestone creates no technical blocker for that work, but it does not authorize or begin it.
