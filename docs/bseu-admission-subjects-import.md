# Импорт требований БГЭУ 2026

`M-BSEU-ADMISSION-SUBJECTS-IMPORT-01` добавляет офлайн-importer для
`docs/data/bseu-admission-subjects-2026.json`. Вход всегда сначала строго
проверяется по `docs/data/bseu-admission-subjects-2026.schema.json` и
дополнительным semantic-инвариантам. Importer не обращается к сети и не
запускает Alembic.

## Предварительные условия и CLI

Выбранная SQLite база должна уже иметь migration
`0007_admission_requirements_schema`, одну University с точными `code=bseu` и
`slug=bseu` и все 17 ранее импортированных Programs.

Из корня репозитория:

```powershell
.\.venv\Scripts\python.exe -m backend.app.cli import-bseu-admission-subjects `
  --database C:\path\to\admission.db --dry-run

.\.venv\Scripts\python.exe -m backend.app.cli import-bseu-admission-subjects `
  --database C:\path\to\admission.db --apply
```

Ровно один режим обязателен. `--apply` не выбирается по умолчанию. Для
контролируемого локального теста можно добавить `--audit-path <path>`; без него
используется tracked canonical audit. Summary детерминированно выводит режим,
безопасный путь базы, путь и SHA-256 аудита, совпавшие Programs, created/reused
по всем сущностям, unchanged rows, conflicts и commit status.

## Dry-run и WAL

`--dry-run` не открывает выбранную базу для записи. Он делает временный
filesystem snapshot main-файла и существующего WAL, затем читает snapshot через
SQLite `mode=ro` с `PRAGMA query_only=ON` и `PRAGMA foreign_keys=ON`.
`immutable=1` не используется, поэтому committed rows из WAL видимы. Исходные
DB, WAL и SHM не создаются и не изменяются; временный snapshot удаляется после
планирования.

## Exact matching и план

University сопоставляется только по точным `code=bseu` и `slug=bseu`. Каждый
Program сопоставляется по точному tracked `Program.slug` внутри BSEU, после чего
обязательно совпадают точные `Program.name` и существующий `Program.code`.
Имя, похожая строка, substring, найденный официальный код или nearest match не
используются. Program не создаётся.

До записи строится полный immutable plan по стабильным audit business keys:

- Subject — `normalized_key`;
- source — BSEU University + `source_id`;
- requirement set — Program slug + admission year + `requirement_set_id`;
- group — requirement-set key + `group_key` и точная position;
- option — group business key + position + subject key;
- evidence link — requirement-set key + source key.

Integer IDs базы используются только как уже проверенные foreign keys, а не
как источник business identity.

## Идемпотентность, конфликты и транзакция

Отсутствующая строка помечается `created`. Полностью совпадающая строка
помечается `reused`; её timestamps не обновляются. Любое различие semantic-поля
по тому же business key является конфликтом: importer ничего не обновляет, не
удаляет и не выполняет частичный commit. Частичный, но согласованный импорт
безопасно дополняется недостающими строками.

`--apply` получает SQLite write lock через `BEGIN IMMEDIATE`, повторно строит
весь план внутри одной транзакции, создаёт только отсутствующие строки и
flush-ит зависимости без промежуточных commits. Перед commit повторно
проверяются `choose_count <= option_count` и `PRAGMA foreign_key_check`. Любая
ошибка откатывает все новые строки. После commit новая read-only session
проверяет полное представление аудита, distinct full/shortened/targeted pathways
и отсутствие новых planned rows. Повторный apply создаёт ноль строк и оставляет
semantic dump и timestamps неизменными.

## Canonical scope и границы

Фактический audit разворачивается в:

- 17 matched Programs;
- 37 requirement sets;
- 11 normalized subjects;
- 3 official evidence sources;
- 92 ordered groups;
- 119 ordered subject options;
- 50 evidence links.

Importer не изменяет `Program`, `ProgramOffering`, mappings, snapshots или
`Program.admission_subjects_json`; найденные официальные коды не копируются в
`Program.code`. Никакие лишние данные другого University, года или будущего
аудита не удаляются.

Безопасная production-процедура, backup/rollback checkpoint и применение к
production откладываются в отдельный milestone
`M-BSEU-ADMISSION-SUBJECTS-PRODUCTION-IMPORT-01`.
