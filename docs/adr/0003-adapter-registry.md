# University integrations use a capability-based adapter registry

## Status
Accepted

## Context

BSEU currently has source-specific fetch/parser behavior embedded in the scraper. New university sources differ in format and available facts. Dispatching with `if/elif` in routes or jobs would spread source knowledge and make failures affect unrelated institutions.

## Decision

Each university integration implements the versioned adapter contract, declares capabilities and returns normalized DTOs with provenance. A centralized registry resolves `adapter_registry.get(university_code)`. Services own orchestration, persistence and notifications; adapters own only official-source transport/parsing/normalization.

## Consequences

- New integrations are isolated and testable with offline fixtures.
- Partial support is explicit instead of represented by fabricated empty values.
- Duplicate/unknown registrations fail clearly.
- Shared concerns such as rate limits, conditional requests and error taxonomy need common core utilities.
- BSEU extraction requires strict parity tests before cutover.

## Alternatives considered

- University-specific branches in a shared scraper: rejected due to coupling and unbounded conditionals.
- One generic configurable scraper: rejected because source schemas and validation rules differ too much for a safe universal parser.
- Separate service per university: rejected as operationally excessive for the VPS and current scale.
