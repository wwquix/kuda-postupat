# BSEU catalog backfill preflight

Проверка выполнена 13 июля 2026 года в часовом поясе Europe/Minsk. Backend и frontend остановлены через `stop-dev.ps1`; PID-файлы отсутствовали или были удалены как устаревшие, порты 8000 и 5173 не слушались.

## Alembic prerequisite

- Активная ветка: `feature/platform-redesign`.
- Рабочее дерево до начала milestone: чистое.
- Alembic установлен в `.venv`.
- До backfill существует один head: `0002_core_catalog_schema`.
- Текущая revision основной БД: `0002_core_catalog_schema`.
- Присутствуют revisions `0001_legacy_baseline` и `0002_core_catalog_schema`.
- `alembic check`: `No new upgrade operations detected`.
- Focused migration suite до изменений: 10 tests passed.
- Предыдущий канонический backup `backups/admission-before-alembic-20260713-102427.db` имеет SHA-256 `a772f8982e28cfeacb7726844118b0121b4d43916014e4e7720bc7fa5d0185f3`, `PRAGMA integrity_check = ok` и ноль нарушений foreign keys.

Обязательные catalog tables существовали и были пусты: `universities`, `university_categories`, `university_category_links`, `programs`, `program_offerings`, `data_sources`.

## Source database inventory

- Settings URL: `sqlite:///./data/admission.db`.
- Фактический путь: `backend/data/admission.db`.
- Размер перед backup: 225,280 bytes.
- SHA-256 перед backup: `bcf4e51df29daf324ecdcc81d88c0d0ef380cac74932a81068ac40de47ae2708`.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 нарушений.

| Table | Rows before backfill |
|---|---:|
| `specialties` | 1 |
| `admission_snapshots` | 4 |
| `scraper_runs` | 62 |
| `notification_logs` | 0 |
| `http_cache_state` | 1 |
| `universities` | 0 |
| `university_categories` | 0 |
| `university_category_links` | 0 |
| `programs` | 0 |
| `program_offerings` | 0 |
| `data_sources` | 0 |

Legacy specialty ID 1 — «Экономическая информатика», `дневная`, `платная`, active. Первый snapshot: ID 1, `2026-07-12 10:57:50.420875`; последний snapshot: ID 4, `2026-07-13 12:09:34.510968`, raw hash `2cd36ba0a73f8ed76b44057ab097caaeb2d80dc7825a86d2b04a1222437defc0`.

Контрольные SHA-256 логического JSON-представления всех legacy rows до backfill:

| Table | Logical SHA-256 |
|---|---|
| `specialties` | `79d91e3bfd6c8d40b95e188c74b8ced3cff50a9b27a06971daa201ff5d6e7cd7` |
| `admission_snapshots` | `b24f777275d7e852b5353f8715c766e6eda50da40f794f0e187054a20d3860b8` |
| `scraper_runs` | `3bec36df89c67f67b79e3791486d8960198519d5d89649bc7e48251a8f6afd8b` |
| `notification_logs` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `http_cache_state` | `771ae32ca90501b0ce11a1693f8751f2af54a77c63f238d1cccd3f4480884396` |

## New canonical backup

- Path: `backups/admission-before-bseu-backfill-20260713-202551.db`.
- Created with Python standard-library `sqlite3.Connection.backup()` from a read-only source connection while the application was stopped.
- Size: 225,280 bytes.
- SHA-256: `54e72c0ed298f39c3d68b7d38efb7d0875b1f75638b8a30405ea3b208f7d128a`.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: 0 нарушений.
- Table list, complete `sqlite_master` schema and every row: exact logical match with source.

Backup и любые SQLite sidecar files исключены из Git.

## Canonical BSEU evidence

- Ministry registry and audited research record confirm `code=bseu`, `slug=bseu`, БГЭУ, full name, state university, Minsk, official site and admissions URL.
- Official program catalog confirms code `6-05-0311-05`, «Экономическая информатика», faculty «Факультет цифровой экономики» and qualification «Экономист. Информатик».
- Official 2026 admission-plan PDF confirms the same code/name and 60 full-time paid places.
- A direct pre-backfill check of `https://bseu.by/abiturient/xml/1.xml` at `2026-07-13 20:24:46 +03:00` returned HTTP 200, 77 rows and exactly one configured target row with plan 60 and 25 applications; source update time was `2026-07-13 18:00:00`.
- The migration will use frozen reviewed values only and will not perform HTTP requests.

## Preflight decision

All mandatory prerequisites are satisfied. Migration C may proceed. The accepted mapping strategy is additive: create `legacy_specialty_mappings`, add nullable `program_offering_id` to `admission_snapshots`, add nullable `data_source_id` to `scraper_runs`, backfill only these new links and preserve every legacy field and identity.
