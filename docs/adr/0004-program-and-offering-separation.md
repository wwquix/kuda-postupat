# Separate academic programs from admission offerings

## Status
Accepted

## Context

The legacy `Specialty` identity includes name, study form and funding type. One academic specialty can appear in several forms, funding types and admission years, and tuition can vary by course. Current observations and final historical cutoffs also have different truth semantics.

## Decision

Model `Program` as the academic specialty at one university. Model `ProgramOffering` as one admission year, study form, funding type and optional audited track. Attach current `AdmissionSnapshot` observations and official `HistoricalCutoff` facts to the offering. Store `TuitionRecord` separately by program/offering, academic year and course/period.

## Consequences

- One program can safely represent budget/paid and yearly offerings without duplication.
- Search and detail pages can group offerings truthfully.
- Migration needs an explicit mapping from every legacy specialty row to one canonical offering.
- Queries are more relational and require indexes/eager loading.
- Current estimates cannot be accidentally displayed as official historical cutoffs.

## Alternatives considered

- Keep one flat specialty row per form/funding/year: rejected due to duplicated academic identity and ambiguous prices/history.
- Put form/funding/year arrays or JSON on Program: rejected because constraints, filtering and foreign keys would be weak.
- Store tuition directly on offering: rejected because course/year price history has an independent lifecycle.
