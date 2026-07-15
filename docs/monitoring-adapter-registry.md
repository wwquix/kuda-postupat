# Monitoring adapter registry

## Scope

The monitoring registry currently contains exactly one operational adapter:
`bseu`. It does not make monitoring available for the other universities in the
catalog. Their catalog and imported Program data remain ordinary read-only data;
the absence of an adapter is not a source outage or an admission result.

## Responsibilities

`BseuMonitoringAdapter` owns the configured BSEU source identity and the typed
parse/select boundary. Its single operation converts the unchanged official
document parser output into `ParsedAdmissionDocument`, with all parsed rows and
the configured monitored rows kept distinct.

`MonitoringAdapterRegistry` owns deterministic key lookup. Construction is
explicit, duplicate keys fail immediately with
`DuplicateMonitoringAdapterKeyError`, and lookup of an absent key raises
`UnknownMonitoringAdapterError`. There are no dynamic imports, directory scans,
plugin loaders or placeholder adapters.

The existing `AdmissionScraper` remains the shared orchestration service. It owns
the HTTP client and retry policy, conditional request state, 304 recovery,
ScraperRun lifecycle, calculations, Snapshot persistence/deduplication, source
health mirroring and Telegram decisions. The adapter does not write the database,
send Telegram messages or choose API responses.

## Stable key and call paths

The stable key is `BSEU_ADAPTER_KEY = "bseu"`.

- Scheduled refresh: APScheduler -> `scheduled_refresh` -> `refresh_bseu` ->
  `AdmissionScraper.refresh("bseu")` -> registry -> BSEU adapter.
- Manual refresh: `POST /api/refresh` -> token validation -> `refresh_bseu` ->
  the same `AdmissionScraper.refresh("bseu")` path.

`DEVELOPMENT_SAFE_MODE=true` still exits the application lifespan before the
scheduler is configured or the startup refresh is created. Read-only development
startup therefore does not resolve or run an adapter and does not contact
Telegram.

## Unknown-key behavior

An unknown key is a controlled orchestration failure. A ScraperRun is committed
as `running` and finalized as `error` with the typed error, matching the existing
run lifecycle. No Snapshot or NotificationLog is created, no Telegram delivery is
attempted, and no DataSource is marked offline because no source was resolved.

## Parity guarantees

The registry cutover preserves the existing BSEU source URL, timeout/retry policy,
parser and specialty filters, calculations, five-minute guard, HTTP cache and 304
semantics, Snapshot hash/deduplication, ScraperRun fields, monitoring status
payloads, source-health mirror, Telegram change/outage/recovery decisions,
scheduler configuration and manual-refresh response contract. The separately
marked live test continues to exercise the official BSEU XML parser.

## Adding a future adapter

Adding another university is a separate roadmap milestone. The minimum sequence
is:

1. Audit and approve one official source, its provenance, rate limits and stable
   university identity.
2. Add offline source fixtures and parser failure cases without weakening BSEU
   fixtures or tests.
3. Implement one class satisfying `MonitoringAdapter`: a unique stable key,
   university code, source/document URLs and the typed `parse` operation.
4. Add the adapter explicitly to registry construction. Do not add filesystem
   discovery or university `if/elif` dispatch.
5. Add an explicitly authorized orchestration entry point using that key and
   prove temporary-database parity for runs, snapshots, conditional requests and
   notification isolation.
6. Run focused tests, the adapter's marked live test and the full verification
   gate before declaring its monitoring coverage online.

These steps describe the contract only; this milestone implements no second
adapter.

## Verification

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest `
  tests/test_monitoring_adapter_registry.py `
  tests/test_scraper_304.py tests/test_http.py tests/test_parser.py `
  tests/test_repository.py tests/test_telegram.py `
  tests/test_development_startup.py tests/test_legacy_api_compatibility.py
```

From the repository root:

```powershell
.\check.ps1
git diff --check
```

Roadmap milestone 9 (Watchlists and per-profile Telegram linking) now has its M4
registry prerequisite. It remains gated by the unfinished parts of milestone 8
and must preserve the owner-mode notification path documented here.
