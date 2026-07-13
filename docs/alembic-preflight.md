# Alembic preflight and SQLite backup verification

Проверка выполнена 13 июля 2026 года в часовом поясе Europe/Minsk. Backend и frontend были остановлены через `stop-dev.ps1`; PID-файлы отсутствовали, порты 8000 и 5173 не слушались.

## Source database inventory

- Settings URL: `sqlite:///./data/admission.db`.
- Фактический путь, разрешённый settings layer независимо от CWD: `backend/data/admission.db`.
- Первичная read-only инвентаризация до Alembic: 61,440 bytes; SHA-256 `63c94746d498e9986ee37f7f58ac9d5dca25b96b32931a79ed0e9f7c523f3c77`.
- `PRAGMA user_version`: `0`.
- `alembic_version`: отсутствовала.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 нарушений.

| Legacy table | Rows |
|---|---:|
| `specialties` | 1 |
| `admission_snapshots` | 2 |
| `scraper_runs` | 31 |
| `notification_logs` | 0 |
| `http_cache_state` | 1 |

Фактические table DDL, PK, FK, FK actions, named/implicit indexes, unique constraints, CHECK constraints, defaults and nullability были сопоставлены с frozen baseline fingerprint. Источником истины для revision `0001_legacy_baseline` является фактическая SQLite schema, а не только ORM metadata.

## Canonical pre-migration backup

- Backup: `backups/admission-before-alembic-20260713-102427.db`.
- Created: `2026-07-13 10:24:27 +03:00`.
- Size: 77,824 bytes.
- SHA-256: `a772f8982e28cfeacb7726844118b0121b4d43916014e4e7720bc7fa5d0185f3`.
- Mechanism: Python standard-library `sqlite3.Connection.backup()` from a read-only source connection while the application was stopped.
- Backup `integrity_check`: `ok`.
- Backup `foreign_key_check`: 0 нарушений.
- Tables, complete `sqlite_master` schema, every legacy row and row counts: exact logical match with source.

Physical SQLite file hashes are not expected to equal each other after the SQLite Backup API rewrites pages and database-header state. Verification therefore uses both a SHA-256 for the immutable backup artifact and an exact logical comparison of schema and rows.

## Restore verification

Backup independently restored through the SQLite Backup API to `backups/restore-check-20260713-102427.db`. The restored database passed:

- `PRAGMA integrity_check = ok`;
- `PRAGMA foreign_key_check` with zero rows;
- exact table-list and `sqlite_master` comparison;
- exact all-row comparison for all five legacy tables;
- exact row-count comparison shown above.

Result: **PASS**. The temporary `restore-check` database was deleted after verification. The canonical backup remains intact and is ignored by Git.

## Recovered pre-migration test artifact

During pre-migration temporary-database validation, two command-routing mistakes reached the configured source database: first an incorrect programmatic Alembic URL precedence, then an invalid PowerShell temporary-URL expression. In both cases baseline creation stopped immediately on the first existing legacy table, after Alembic had created only an empty `alembic_version` table. Each time only that confirmed-empty service table was removed. All five legacy table schemas and all rows were then compared exactly with the verified backup: IDs, JSON, hashes and timestamps matched, and integrity/FK checks passed.

The URL precedence was fixed and covered by migration tests; the CLI cycle was then repeated with an explicit settings-layer target assertion and passed only on an isolated temporary database. The service-table create/drop operations changed SQLite's physical page/header layout, so the source file byte hash changed, but they did not change any legacy schema or row value. The canonical backup remains an exact logical pre-migration image.
