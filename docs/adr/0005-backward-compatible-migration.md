# Migrate additively with a compatibility layer

## Status
Accepted

## Context

The existing BSEU monitor, database history, PowerShell scripts, scheduler, Telegram owner mode and React dashboard must remain functional after every commit. A direct replacement of tables/routes would risk data loss and a long unverified cutover.

## Decision

Use additive Alembic phases: baseline/stamp, catalog tables, BSEU identity and mapping/backfill, additional fact/source tables, user/notification tables, and only later explicit compatibility cleanup. Preserve legacy tables and IDs through the early phases. Keep old endpoints/payloads via wrappers or a compatibility service until new consumers and a complete admission cycle are verified.

## Consequences

- Every milestone has a bounded rollback and can be checked against old behavior.
- Temporary duplicate columns/mappings and compatibility code increase short-term complexity.
- Dual ownership must be explicit; no silent mixture of legacy and canonical writes.
- Destructive cleanup is deferred and requires separate approval, archive and restore plan.
- Regression tests must compare legacy endpoint payloads and snapshot hashes/timestamps.

## Alternatives considered

- Big-bang schema and API rewrite: rejected because it violates the invariants and combines too many failure modes.
- Export/import into a new database: rejected because it changes paths/operations and risks losing audit identities.
- Permanent legacy schema: rejected because it cannot truthfully model catalog domains and multiple offerings.
