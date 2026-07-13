# Canonical Belarus university catalog import result

Milestone executed locally on 13 July 2026 (Europe/Minsk). The import used the tracked research dataset only, performed no HTTP requests and did not run FastAPI lifecycle, scheduler or Telegram. No Alembic revision was added because the existing catalog schema already supports the accepted fields.

## Recovery artifact

- Backup: `backups/admission-before-university-catalog-import-20260713-210717.db`.
- SHA-256: `2558f955c865273ea797c5f9397b56fdd1fb8ab84c866fd009ab97cd35fe4f8e`.
- Size: 262,144 bytes.
- Alembic revision: `0003_backfill_bseu_catalog` before and after import.
- Validation: `PRAGMA integrity_check = ok`, zero foreign-key violations, full table/row comparison with the stopped source database was exact.
- Backup is excluded from Git.

The source DB before backup/import had SHA-256 `9703d786f5344f48e4ee43239e84f199815d429ad1280fc6d95273c2f647047f` and size 262,144 bytes.

## Source and validation

- Canonical source: `backend/data/research/universities-canonical-2026.json`.
- Research JSON Schema: `backend/data/research/universities-canonical.schema.json`, version `1.0`.
- Single-university import/export Schema: `backend/data/schemas/university-import.schema.json`, version `1.0`.
- Existing research validator: PASS, exit code 0.
- New import validation: PASS.
- Confirmed input: 47 universities, 43 state, 4 private, 11 cities, 33 admissions URLs.
- Review items: 5, kept only in the research JSON and skipped by every seed.

## Import summaries

| Run | Created | Updated | Unchanged | Conflicts | Categories created/updated | Links created | Sources created | Review items skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dry run | 46 | 1 | 0 | 0 | 14 / 1 | 63 | 127 | 5 |
| First import | 46 | 1 | 0 | 0 | 14 / 1 | 63 | 127 | 5 |
| Second import | 0 | 0 | 47 | 0 | 0 / 0 | 0 | 0 | 5 |

The one updated University in dry run/first import was existing BSEU: the canonical research verification timestamp populated its previously null `data_verified_at`. Its identity, monitoring status and existing source runtime state were not replaced. The category row `economic` was retained and its editorial label normalized from the migration-era «Экономика» to the centralized «Экономический» label.

The database SHA-256 immediately after the first import was `2bf20dbfad35a995efa6b4b11ccc011a4f04d30912970f09c9ccae67bb0388b7`. It was identical after the second seed, proving that the completely unchanged rerun did not write `updated_at` or other rows.

## Counts before and immediately after import

| Table / metric | Before | After first import | After second import |
|---|---:|---:|---:|
| `universities` | 1 | 47 | 47 |
| state / private | 1 / 0 | 43 / 4 | 43 / 4 |
| distinct cities | 1 | 11 | 11 |
| universities with admissions URL | 1 | 33 | 33 |
| `university_categories` | 1 | 15 | 15 |
| `university_category_links` | 1 | 64 | 64 |
| `data_sources` | 1 | 128 | 128 |
| `programs` | 1 | 1 | 1 |
| `program_offerings` | 1 | 1 | 1 |
| `legacy_specialty_mappings` | 1 | 1 | 1 |
| `specialties` | 1 | 1 | 1 |
| `admission_snapshots` | 5 | 5 | 5 |
| `scraper_runs` | 64 | 64 | 64 |
| `notification_logs` | 0 | 0 | 0 |
| `http_cache_state` | 1 | 1 | 1 |

Final monitoring statuses after import: 1 `online` (BSEU), 25 `reference_only`, 21 `needs_review`. The nine preliminary research candidates and twelve `needs_research` entries were conservatively mapped to `needs_review`; none became `online`.

## BSEU preservation

| Record | Before | After import |
|---|---:|---:|
| University ID | 1 | 1 |
| Program ID | 1 | 1 |
| ProgramOffering ID | 1 | 1 |
| XML DataSource ID | 1 | 1 |
| Legacy specialty/mapping ID | 1 | 1 |

BSEU remained `code=bseu`, `slug=bseu`, monitoring `online`. XML adapter identity `legacy_admission_scraper`, ETag, Last-Modified, health, last attempt and last success timestamps were unchanged by both seeds. The 127 new DataSources are additive official registry/site/admissions references with no adapter identity or fabricated runtime health.

## Legacy preservation

The values below were calculated over every column and row before import and immediately after import; every digest is unchanged.

| Table | Logical SHA-256 before/after |
|---|---|
| `specialties` | `79d91e3bfd6c8d40b95e188c74b8ced3cff50a9b27a06971daa201ff5d6e7cd7` |
| `admission_snapshots` | `a304ecd3c63f5796e478b5d44673d0d193383513be39806d8a2cc4d604a46e65` |
| `scraper_runs` | `6bc0e5ce74c31c47ec051aa56a0ae2d1830081adbc7aad1425afa102b777f159` |
| `notification_logs` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Latest snapshot stayed ID 5 with raw hash `3f7235e81a8cb40f6f459a3283a9092293e5261977fd7c93637c2fd1204c8669`, `fetched_at=2026-07-13 17:46:40.098531` and `source_updated_at=2026-07-13 18:00:00.000000`.

## Merge and transaction policy

- `University.code` is the immutable business key; slug is the secondary collision guard.
- Existing code with another slug or a slug owned by another code aborts the complete import.
- Schema/JSON errors, conflicts and database constraint failures leave the catalog transaction uncommitted.
- Non-empty known values are never replaced with null/blank input.
- Catalog fields are updated only when the incoming verification is not older than `data_verified_at`; newer verified manual values are retained.
- BSEU slug and `online` status are protected explicitly; no other university can import as `online`.
- Categories, category links and sources are additive. Existing manual category links and sources are not deleted.
- URL identity is normalized by scheme/host/default port/path and removes fragments and tracking parameters.
- Canonical seed persists official registry, official site and admissions page references. Detailed availability, automation assessment, research notes, HTTP checks and additional research links remain in the versioned research JSON.
- One-university Program/Offering payloads are read-only assertions: export includes them, but arbitrary import cannot create or modify them.

## Catalog audit

`python -m app.cli audit-catalog` completed with exit code 0 and no errors:

- 47 universities; 43 state; 4 private; 11 cities; 33 admissions URLs;
- duplicate code/slug/category links/DataSources: 0;
- invalid required URLs: 0;
- all universities have an official registry DataSource and source check time;
- only BSEU is `online` and it retains Program/Offering/XML adapter identity;
- review items are absent from production catalog.

Expected warnings remain explicit: 14 universities lack a confirmed admissions URL, 46 have no imported programs, and 46 have no admission adapter. No unknown value was replaced with a zero, false claim or invented URL.

## Export/import verification

`export-university bseu` produced stable Schema-valid JSON containing BSEU University, its `economic` category, four source identities, Program ID 1 and Offering ID 1. It excludes ETag, Last-Modified, runtime errors, Telegram data, secrets and full legacy snapshots. Re-import of the exported document on a disposable database was idempotent: University/Program/Offering IDs and counts stayed unchanged.

## Runtime and regression verification

- Application startup did not run seed: universities/categories/links/sources remained 47/15/64/128.
- Exactly one APScheduler job was registered and one backend/frontend listener was present.
- Startup refresh: upstream HTTP 200, 77 rows, zero duplicate snapshots; scraper runs 64 → 65, snapshots stayed 5, notifications stayed 0.
- Manual `refresh.ps1` after the five-minute source limit: API/upstream HTTP 200, `status=success`, 77 rows, zero snapshots created; scraper runs 65 → 66, snapshots stayed 5 and notifications stayed 0.
- The official server did not return HTTP 304 during this runtime window. Conditional 304 behavior, validator updates, snapshot deduplication and notification suppression remain covered by the six passing dedicated scraper 304 tests; no false live-304 claim is made.
- Seven legacy BSEU GET endpoints and six existing BSEU catalog GET endpoints returned HTTP 200.
- Existing React dashboard rendered the specialty, plan 60, 25 applications and all five history rows in a real browser; there was no horizontal page overflow, visible error/alert or console warning/error.
- Focused catalog import suite: 14 passed.
- Full ordinary backend suite: 64 passed, 1 deselected; only existing Python 3.13 SQLite datetime deprecation warnings.
- Live BSEU integration: 1 passed, 64 deselected.
- Ruff, ESLint, TypeScript and Vite production build: passed.
- Alembic single-head/current/check and SQLite integrity/foreign-key checks: passed.

## Known limitations and stop boundary

- The current schema has no per-reference-source checked timestamp; stable export uses the University verification time for registry/site/admissions references. BSEU XML uses its actual last successful/attempted check time. Runtime health state is not exported.
- The official BSEU source returned HTTP 200 rather than 304 in the runtime window; the 304 contract is test-covered rather than live-observed for this milestone.
- `needs_review` preserves preliminary research uncertainty; it does not mean an adapter exists or monitoring is available.
- Programs and offerings for the other 46 universities remain intentionally absent.
- Vite reports the existing main-chunk size warning above 500 kB; frontend code was not changed.
- No catalog/search API, frontend, new adapters, additional source research or VPS deployment was started.
