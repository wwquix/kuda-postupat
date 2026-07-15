# Catalog and search API

This document describes the read-only public catalog contract implemented for the future frontend. The API reports only data imported into this platform. An empty list or a zero imported count is not a claim that a university has no real programs.

## Base contract

All endpoints are under `/api` and return JSON. Unknown university slugs and program IDs return HTTP 404. Invalid enum, pagination, sorting or numeric filter values return HTTP 422.

Pagination is mandatory for collection endpoints:

- `page >= 1`, default `1`;
- `page_size >= 1`, default `20`, maximum `100`;
- a page beyond the result returns HTTP 200 with an empty `items` list;
- ordering always includes an internal stable ID tie-breaker.

The pagination object is:

```json
{
  "page": 1,
  "page_size": 20,
  "total_items": 47,
  "total_pages": 3,
  "has_next": true,
  "has_previous": false
}
```

Counts in examples reflect the verified local catalog at the milestone checkpoint, but responses are calculated from the database.

## Universities

### `GET /api/universities`

Returns:

```json
{
  "items": [],
  "pagination": {}
}
```

Supported parameters:

| Parameter | Meaning |
|---|---|
| `q` | Search names, code, slug, city, region, category and imported program name/code/slug. |
| `city` | Normalized exact city match. |
| `region` | Normalized exact region match. |
| `ownership_type` | `state`, `private`, `mixed` or `unknown`. |
| `institution_kind` | Persisted institution-kind enum. |
| `category` | Category code or Russian label. |
| `monitoring_status` | Persisted platform monitoring status. |
| `has_admissions_url` | Whether an admissions URL is imported. |
| `has_programs` | Whether at least one Program is imported into the platform. |
| `online_monitoring` | Whether a working enabled adapter backs an `online` university. |
| `active` | Catalog active flag. |
| `page`, `page_size` | Required pagination contract. |
| `sort`, `order` | Whitelisted sort and `asc`/`desc`. |

Allowed university sort values are `name`, `city`, `region`, `ownership`, `monitoring_status`, `program_count` and `updated_at`. A user-provided SQL column name is never accepted.

Search normalization applies Unicode NFKC, case folding, whitespace collapse, `ё → е` and common dash normalization. `%`, `_` and the escape character are escaped before SQL `LIKE`. Filtering, search, count, sorting, offset and limit run in SQL.

Examples:

```text
GET /api/universities?q=БГЭУ
GET /api/universities?city=Минск&ownership_type=private
GET /api/universities?category=economic
GET /api/universities?has_programs=true
GET /api/universities?online_monitoring=true
GET /api/universities?sort=program_count&order=desc
```

Each item contains imported `program_count` and `offering_count` plus explicit `coverage` states. A zero count means `not_imported`, not real-world absence.

### `GET /api/universities/{slug}`

Returns public university fields, categories, safe source identities, verification times, imported counts, explicit platform coverage and a required `programs` array. The nested array reuses `ProgramResponse`; each Program contains deterministic imported `OfferingSummaryResponse` items. Empty `programs` means `not_imported` platform coverage, not real-world absence. Public sources contain only:

```text
source_type
source_url
checked_at
```

The response excludes ETag, Last-Modified, runtime error messages, filesystem paths and secrets.

### `GET /api/universities/{slug}/programs`

Returns a paginated Program collection. If this platform has not imported programs for the university, `items` is empty and `coverage.note` explicitly says that the empty platform result does not prove real-world absence.

## Programs

### `GET /api/programs`

Supported parameters:

| Parameter | Meaning |
|---|---|
| `q` | Search imported program name/code/slug and university name. |
| `university` | University code or slug. |
| `city` | University city. |
| `admission_year` | Offering year from 2000 through 2100. |
| `study_form` | Persisted study-form enum. |
| `funding_type` | Persisted funding-type enum. |
| `monitoring_status` | Offering monitoring status. |
| `has_offerings` | Whether at least one offering is imported. |
| `page`, `page_size` | Required pagination contract. |
| `sort`, `order` | Program sort whitelist and `asc`/`desc`. |

Allowed program sort values are `name`, `university`, `city`, `offering_count` and `updated_at`.

The response contains `items`, `pagination` and database-derived `coverage`:

```json
{
  "universities_total": 47,
  "universities_with_imported_programs": 1,
  "programs_total": 1,
  "offerings_total": 1,
  "state": "partial",
  "note": "Счётчики описывают только импортированное покрытие платформы, а не полный реальный каталог программ вузов."
}
```

### `GET /api/programs/{id}`

Returns the imported Program, university identity and its imported offering summaries. It does not include admission snapshot history; the existing `/api/program-offerings/{id}/...` endpoints remain responsible for monitoring history.

## Metadata

### `GET /api/catalog/meta`

Returns database-derived:

- cities and regions;
- ownership and institution types;
- categories and monitoring statuses;
- admission years, study forms and funding types present in imported offerings;
- university, Program and ProgramOffering counts;
- universities with imported programs and admissions URLs;
- pagination limits and coverage totals.

No catalog count is hardcoded.

## Health

### `GET /api/catalog/health`

Performs local checks only:

- database query succeeds;
- current Alembic revision equals the single code head;
- catalog counts can be read;
- canonical BSEU University/Program/Offering and production adapter identity exist;
- duplicate catalog identities are absent.

The status is `healthy`, `degraded` or `unhealthy`. The response does not contact university websites and does not expose exception text, source validators, stack traces or paths.

## Data-honesty boundary

- No API request creates or imports data.
- Only BSEU currently has imported Program/ProgramOffering rows and an online production adapter.
- `reference_only` and `needs_review` describe platform monitoring coverage; they are not statements about a university's real admission offering.
- Missing tuition, scholarships, dormitories and media are not returned as `false`, zero or empty verified facts.
- Catalog coverage counts describe this platform, not complete real-world university coverage.

## Compatibility

The catalog router remains additive. Existing BSEU monitor endpoints and the ProgramOffering history endpoints keep their paths. The catalog test application uses dependency overrides and isolated temporary SQLite databases; importing the router does not start FastAPI lifespan, APScheduler, Telegram or database writes.
