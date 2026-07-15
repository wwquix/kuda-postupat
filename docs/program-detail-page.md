# Program detail page

M-PROGRAM-DETAIL-01 adds one read-only public Program vertical slice. It uses the existing catalog schema and imported data; it adds no migration, import, adapter, monitoring calculation or user feature.

## Public identity and routes

- Frontend: `/universities/:universitySlug/programs/:programKey`.
- API: `GET /api/universities/{university_slug}/programs/{program_slug}`.

`programKey` is the canonical stored `Program.slug`. The database enforces uniqueness of this slug inside one University, so the public identity is the pair `(university_slug, program_slug)`. The existing `GET /api/programs/{id}` endpoint remains available for compatibility, but new frontend navigation does not expose numeric IDs.

The service first resolves an active University, then resolves an active Program by that University ID and canonical slug. Unknown University, unknown Program and a Program belonging to another University all return HTTP 404.

## Response and ordering

The endpoint reuses the established `ProgramResponse` schema:

- Program identity, code and nullable stored metadata;
- owning University identity;
- official Program URL and stored verification/check timestamps;
- `offering_count` and imported `OfferingSummaryResponse` items;
- explicit `coverage_state` describing platform coverage.

Offerings are ordered deterministically by admission year, study form, funding type and stable ID. The public Offering summary contains stored year, study form, funding type, nullable places, platform monitoring capability/status, official/source URLs and source check time.

The ORM has no language-of-study field and the public schema does not expose application deadlines. Those facts are omitted rather than inferred. Admission history and score distributions remain on the existing ProgramOffering monitoring endpoints and are not implied by this page.

## Page behavior

The page renders:

1. Program name and code when stored.
2. Owning University with an internal link.
3. Nullable qualification, faculty, education level and duration only when present.
4. Official Program resource and stored check date.
5. Imported offerings with stored year/form/funding, nullable places, platform monitoring status and official resource.
6. A `/monitor` link only when an imported Offering explicitly has both `monitoring_supported=true` and `monitoring_status=online`.

It has distinct announced loading, retryable error, HTTP 404 and success states. Every request uses `AbortController`; route changes abort obsolete requests. Raw API errors are not displayed.

University Program names link to the nested route and pass the exact current University `pathname + search` as validated navigation state. `Назад к вузу` preserves that URL. Direct opening, refresh or invalid state falls back to `/universities/{owning-slug}`.

## Honest empty and missing states

An empty imported Offering collection renders exactly:

```text
Варианты обучения ещё не импортированы
```

The accompanying explanation says that this is platform coverage, not proof that real variants do not exist. Missing fields are omitted; no unknown tuition, scholarships, dormitory, media, language, deadlines, places or historical scores are replaced with false, zero or plausible-looking values.

## Side-effect isolation

Backend tests build a small FastAPI application around the catalog router, override `get_db` and use a temporary SQLite database. They verify success, zero offerings, deterministic order, all ownership-aware 404 cases, OpenAPI, bounded queries, no SQL writes and no external connection.

Frontend tests mock the nested GET response and cover loading, success, empty offerings, retry, 404, exact return navigation, direct fallback, stale-request abort, honest rendering and the absence of downstream Offering-detail/history links.

Runtime smoke testing uses exactly one `start-dev.ps1` application instance. Development safe mode keeps APScheduler, startup refresh and Telegram side effects disabled. No catalog test runs concurrently against that instance, and smoke testing never calls `POST /api/refresh`.

## Deliberately deferred

Recommendations, comparison, favorites, profiles, authentication, watchlists, Telegram linking, tuition/scholarship/dormitory/media expansion, new imports/adapters, deployment and ProgramOffering history UI remain outside this milestone.
