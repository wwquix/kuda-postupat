# SQLite remains the primary database for the first release

## Status
Accepted

## Context

The working monitor persists snapshots, HTTP cache, runs and notification fingerprints in SQLite with WAL and foreign keys. The expected catalog and single-worker workload fit a small VPS. Switching databases during a compatibility-sensitive redesign would combine infrastructure migration with schema/domain migration.

## Decision

Retain SQLite for the first platform release. Use SQLAlchemy repositories, bounded queries, explicit indexes, short transactions and Alembic migrations. Keep the existing configured database paths. Search uses FTS5 when available and an indexed fallback otherwise.

## Consequences

- Existing data and operational backup practices remain usable.
- One writer/process and WAL match the deployment model.
- Migrations that alter constrained tables may require SQLite table rebuilds, backup and careful verification.
- Write-heavy concurrency and horizontal scaling are intentionally unsupported in this phase.
- The repository/service boundary must avoid database-specific behavior where inexpensive, without pretending portability is already proven.

## Alternatives considered

- PostgreSQL now: rejected because it adds service administration, migration risk and resource use without a demonstrated workload need.
- Embedded non-relational storage: rejected because relations, provenance, uniqueness and transactional backfills are central.
- Elasticsearch for search: rejected because SQLite FTS5/fallback is adequate and far lighter operationally.
