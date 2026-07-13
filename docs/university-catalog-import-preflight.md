# Canonical university catalog import preflight

Проверка выполнена 13 июля 2026 года в часовом поясе Europe/Minsk. Backend и frontend остановлены через `stop-dev.ps1`; PID-файлы отсутствуют, порты 8000 и 5173 не слушаются.

## Git and Alembic prerequisite

- Ветка: `feature/platform-redesign`.
- Исходное рабочее дерево: чистое.
- Исходный commit: `a338ee4384d074cbbd36e078e6f4026e224f4667 feat: backfill BSEU into catalog model`.
- Git root соответствует этому репозиторию.
- Alembic имеет один head: `0003_backfill_bseu_catalog`.
- Основная БД находится на `0003_backfill_bseu_catalog`.
- `alembic check`: `No new upgrade operations detected`.

## Canonical research prerequisite

- Source: `backend/data/research/universities-canonical-2026.json`.
- Research schema: `backend/data/research/universities-canonical.schema.json`, version `1.0`.
- Existing validator: PASS, exit code 0.
- Canonical universities: 47 confirmed; 43 state; 4 private; 11 cities; 33 admissions URLs.
- Automation assessment: 1 online (BSEU), 9 candidates, 25 reference-only, 12 needing research.
- Review items: 5. They are stored only in the separate `review_items` array and have no overlap with canonical university identities.
- Used editorial categories: 15, with 64 university/category links.

The import reads only `active_status=confirmed` records from `universities`. It does not import `review_items`, research notes, HTTP result details, preliminary data-availability assessments or adapter feasibility claims.

## Source database inventory

- Settings URL resolves to `backend/data/admission.db`.
- Size before import: 262,144 bytes.
- SHA-256 before import: `9703d786f5344f48e4ee43239e84f199815d429ad1280fc6d95273c2f647047f`.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 violations.

| Table | Rows before import |
|---|---:|
| `universities` | 1 |
| `university_categories` | 1 |
| `university_category_links` | 1 |
| `programs` | 1 |
| `program_offerings` | 1 |
| `data_sources` | 1 |
| `legacy_specialty_mappings` | 1 |
| `specialties` | 1 |
| `admission_snapshots` | 5 |
| `scraper_runs` | 64 |
| `notification_logs` | 0 |
| `http_cache_state` | 1 |

Latest legacy snapshot: ID 5, raw hash `3f7235e81a8cb40f6f459a3283a9092293e5261977fd7c93637c2fd1204c8669`, fetched at `2026-07-13 17:46:40.098531`, source-updated at `2026-07-13 18:00:00.000000`.

Logical SHA-256 values before import, including all existing columns:

| Table | Logical SHA-256 |
|---|---|
| `specialties` | `79d91e3bfd6c8d40b95e188c74b8ced3cff50a9b27a06971daa201ff5d6e7cd7` |
| `admission_snapshots` | `a304ecd3c63f5796e478b5d44673d0d193383513be39806d8a2cc4d604a46e65` |
| `scraper_runs` | `6bc0e5ce74c31c47ec051aa56a0ae2d1830081adbc7aad1425afa102b777f159` |
| `notification_logs` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

## BSEU identity checkpoint

- University: ID 1, `code=bseu`, `slug=bseu`, monitoring `online`.
- Program: ID 1, code `6-05-0311-05`.
- ProgramOffering: ID 1, year 2026, `full_time + paid`, monitoring `online`.
- DataSource: ID 1, `admission_xml`, adapter `legacy_admission_scraper`.
- Legacy mapping: specialty ID 1 → program ID 1 → offering ID 1.
- Existing XML ETag, Last-Modified, health and attempt/success timestamps were inventoried and must not be changed by the catalog seed.

## Recovery artifact

- Backup: `backups/admission-before-university-catalog-import-20260713-210717.db`.
- Size: 262,144 bytes.
- SHA-256: `2558f955c865273ea797c5f9397b56fdd1fb8ab84c866fd009ab97cd35fe4f8e`.
- Created with `sqlite3.Connection.backup()` from a read-only source while services were stopped.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 violations.
- Table list and every row: exact match with the source database.
- The backup is excluded by `.gitignore` and is not part of the commit.

## Persisted-field ownership decision

| Research field | Persisted catalog field / behavior |
|---|---|
| `code` | `University.code`; immutable business key |
| `slug` | `University.slug`; conflict check, never silently changed |
| `short_name`, `full_name` | Corresponding non-empty University fields |
| `institution_kind` | Existing `InstitutionKind` enum |
| `ownership_type` | Existing `OwnershipType` enum |
| `city`, `region` | Corresponding University fields; null/blank never erases known data |
| `official_site_url` | Normalized `University.official_site_url` and an `official_site` DataSource |
| `admissions_url` | Normalized optional University field and an `admissions` DataSource when present |
| `official_registry_url` | `University.source_url` and an `official_registry` DataSource |
| `source_checked_at` | `University.source_checked_at`; also used as catalog-source provenance in stable export |
| `active_status=confirmed` | `University.active=true`; no other status is imported |
| `categories` | Additive category/link upsert using the centralized label mapping |
| automation `online` | Allowed only for BSEU; BSEU remains `online` |
| automation `reference_only` | `MonitoringStatus.reference_only` |
| automation `candidate` / `needs_research` | Conservatively `MonitoringStatus.needs_review`, never `online` |

`data_availability`, detailed `automation_assessment`, HTTP checks, research notes, nested research source inventory and all review items remain in the versioned research JSON. The production seed persists only official registry/site/admissions references supported by the current model. It does not create adapters, programs, offerings or speculative facts.

## Preflight decision

All blocking prerequisites are satisfied. The import may proceed through a validated CLI/service transaction. No Alembic data migration is required or permitted for the remaining 46 universities.
