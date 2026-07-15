# University detail page

M-DETAIL-01 adds one read-only public university vertical slice. It reuses the existing catalog domain and does not add migrations, imports, adapters or user features. M-PROGRAM-DETAIL-01 later adds links from its imported Program names to the separate read-only Program page.

## Public routes

- Frontend: `/universities/:slug`.
- API: `GET /api/universities/{slug}`.

The API endpoint already existed before this milestone. Its `UniversityResponse` contract is extended compatibly with a required `programs` array; all previous response fields keep their meaning. An unknown canonical stored slug returns HTTP 404. The request performs database reads only and never starts scraping or imports data.

## Response ownership and ordering

The catalog repository resolves an active University by its stored slug and eagerly loads its categories, public DataSources, active Programs and ProgramOfferings. The catalog service remains responsible for Pydantic response mapping and for the established platform-coverage states.

The response includes:

- university identity, location, ownership, institution kind and categories;
- official and admissions URLs already stored on University;
- monitoring status and explicit platform coverage;
- safe public source identities with `source_type`, `source_url` and `checked_at` only;
- University verification/check timestamps;
- active imported Programs using the existing `ProgramResponse` schema;
- imported ProgramOffering summaries using the existing `OfferingSummaryResponse` schema.

Nested Programs are ordered by normalized name and stable ID. Offerings are ordered by admission year, study form, funding type and stable ID. Empty `programs` is a valid successful response and means only that this platform has not imported program coverage.

## Page sections

The frontend displays only fields present in the detail response:

1. University identity and categories.
2. Official resources.
3. Monitoring, platform coverage, source links and stored dates.
4. Imported Programs and their imported offering summaries.

Nullable identity or Program fields are omitted when absent. A Program name links to `/universities/:universitySlug/programs/:programSlug` only when its canonical stored slug is present; malformed missing identity remains plain text. There are no links to the legacy numeric frontend shape `/programs/:id`. BSEU receives a `/monitor` link only when the established API coverage says online monitoring is available.

The Program link carries the exact current University `pathname + search` in validated React Router state. The Program page uses it for `Назад к вузу`; direct opening safely falls back to the owning University route.

## Catalog return navigation

Only the university name inside each catalog card is an internal link. The catalog passes its exact `pathname + search` in React Router navigation state. The detail page validates that the state points to `/universities` and uses it for the semantic `Назад к каталогу` link.

Direct opening or refresh without valid navigation state falls back to `/universities`. Catalog URL synchronization and browser Back/Forward behavior are unchanged.

## Honest coverage and request states

The required empty-program text is:

```text
Каталог программ ещё не импортирован
```

The required missing-admissions text is:

```text
Ссылка для абитуриентов пока не добавлена
```

The page never renders an empty imported collection as `Специальностей нет`, never displays an imported count of zero as a real-world fact, and does not infer tuition, scholarships, dormitories, media or admissions facts.

The route has distinct initial loading, success, safe retryable error, HTTP 404 and empty imported-program states. Raw API errors are not rendered. An AbortController cancels the obsolete request when the slug changes.

## Tests

Focused backend contract and isolation check:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pytest tests\test_catalog_search_api.py
Pop-Location
```

Focused frontend behavior check:

```powershell
Push-Location frontend
npm run test -- UniversityDetailPage.test.tsx UniversitiesPage.test.tsx
Pop-Location
```

Complete regression suite:

```powershell
.\check.ps1
```

Backend tests use a temporary SQLite database and dependency override. Frontend tests mock every response. Neither suite starts lifespan/APScheduler, calls BSEU, invokes Telegram or writes the main database.

## Deliberately deferred

Recommendations, comparison, favorites, profiles, authentication, watchlists, Telegram linking, new adapters/imports and deployment remain outside M-DETAIL-01. The separate Program detail slice is documented in [program-detail-page.md](program-detail-page.md).
