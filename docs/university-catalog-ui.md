# University catalog interface

The public university catalog is available at `/universities`. It is a collection page only: this milestone does not register `/universities/:slug`, turn university names into internal links or start a university detail interface.

## API dependencies

The page uses only the shared typed client methods for:

- `GET /api/catalog/meta` — database-derived filter options, counts, coverage and pagination limits;
- `GET /api/universities` — backend search, filtering, sorting and pagination.

The browser does not read the research JSON and does not filter, sort or paginate university rows locally. Each result request carries `page`, the metadata-provided default `page_size`, `sort` and `order`. An `AbortController` cancels a result request when URL parameters change before it completes.

The actual list response does not contain `data_verified_at`, `source_checked_at` or another verification timestamp. The catalog therefore does not invent or infer a date and does not issue forbidden per-university detail requests to obtain one. A future detail page can use the verified provenance fields in its own API contract.

## URL parameters

The URL is the canonical state for:

| Parameter | UI behavior |
|---|---|
| `q` | Debounced backend search; 300 ms delay. |
| `city` | Exact option from catalog metadata. |
| `region` | Exact option from catalog metadata. |
| `ownership_type` | Persisted option returned by metadata. |
| `institution_kind` | Persisted option returned by metadata. |
| `category` | Category code returned with its Russian label by metadata. |
| `monitoring_status` | Platform monitoring state returned by metadata. |
| `has_admissions_url` | `true` or `false`. |
| `has_programs` | Imported platform program coverage, `true` or `false`. |
| `online_monitoring` | Working platform monitoring coverage, `true` or `false`. |
| `sort` | `name`, `city`, `monitoring_status`, `program_count` or `updated_at`. |
| `order` | `asc` or `desc`. |
| `page` | Server page; default page 1 is omitted, non-default pages are serialized. |

Serialization order is stable. Empty/default values are omitted. Invalid page, sort, order, boolean and metadata-backed filter values are removed before the result request. Search, filter and sort changes reset the page to 1. Direct refresh and browser Back/Forward restore the controls from the URL without a second client-side state store.

## Search, filters and sorting

Search is committed after 300 ms or immediately on form submit. Submitting while a debounce timer exists cancels that timer, so Enter does not create a duplicate request. The clear-search button removes `q` and resets the page.

The desktop filter area is visible. At narrow widths the same semantic controls live in a native collapsible `details` panel. All option values come from `/api/catalog/meta`; category labels come directly from the response, while persisted enum tokens are translated for display only after the metadata value is present. Boolean controls describe platform coverage rather than real-world absence.

Active search and filter states are shown as removable controls. One action clears search and every filter while retaining the selected sort.

Sorting is always performed by `/api/universities`. Both ascending and descending order are available for the five public UI sort choices.

## Pagination

The page follows the public server contract:

- page numbering begins at 1;
- the default page size comes from metadata and is currently 20;
- results are never sliced locally;
- total matches, current page and total pages come from the API response;
- previous, next and compact numbered controls are native buttons;
- a page beyond the available result is replaced safely with the last available page;
- an invalid URL page recovers to page 1 before a request is sent.

## Card and coverage wording

Cards display only list-response fields: short/full name, city/region, ownership, institution kind, categories, platform monitoring status, imported program count and official/admissions URL availability.

Required honest states are literal:

- zero imported programs: `Каталог программ ещё не импортирован`;
- missing admissions URL: `Ссылка для абитуриентов пока не добавлена`;
- BSEU with confirmed online coverage: a link to `/monitor`;
- no university name links to an unfinished detail route.

The page also states that counts and monitoring statuses describe this platform's incomplete coverage. It never renders zero imported programs as proof that a university has no real programs, and only BSEU receives the live-monitor link.

## Loading, error and empty states

Initial metadata/results loading is announced. Parameter changes keep the previous page visible with an explicit background-loading status while the old request is cancelled. Metadata and result errors use recoverable retry actions and never expose raw errors or masquerade as an empty catalog. Empty results have their own explanation and clear-filters action.

## Tests

Run the focused frontend suite and the complete project checks:

```powershell
Push-Location frontend
npm run test
npm run lint
npm run typecheck
npm run build
Pop-Location

.\check.ps1
```

Vitest and React Testing Library supply every metadata and university response through a strict `fetch` mock. Tests cover routing/navigation, loading, retry/error, empty results, debounce, cancellation, every public filter, combined filters, clearing, sorting, pagination/recovery, refresh state, Back/Forward state, honest wording, BSEU monitor linking and the absence of detail links. They do not import FastAPI, open SQLite, start lifespan/APScheduler, invoke Telegram or contact a university.

## Deferred detail milestone

University details remain deferred. The next milestone may implement `/universities/:slug` only after inspecting its real API response and provenance fields; it must not infer missing programs, tuition, dormitory, scholarship or media data from catalog list coverage.
