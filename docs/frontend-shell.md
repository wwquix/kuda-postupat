# Frontend shell and routing

This milestone adds the routed frontend foundation for «Куда поступать» while preserving the existing BSEU monitor. It intentionally does not start the university catalog UI.

## Implemented routes

| Route | Page |
|---|---|
| `/` | Finished minimal homepage with platform scope, database-derived university count, BSEU-only live-monitoring notice and official-data limitations. |
| `/monitor` | Existing BSEU admission dashboard, including score scenario, snapshots, charts, history, freshness, source link and manual refresh. |
| `*` | Safe frontend 404 with links to the two implemented routes. |

No placeholder routes exist for future catalog, program, recommendation, profile or user-state features.

## Layout structure

`SiteLayout` owns the semantic site header, two-item primary navigation, main content landmark and footer. `NavLink` provides `aria-current="page"` for the active route. The navigation remains visible and wraps on narrow screens, so it does not require a JavaScript-only mobile menu.

Every page has exactly one `h1`, a route-specific document title and a valid heading hierarchy. A keyboard-visible skip link targets the main content, and links, buttons, form controls and other focusable elements receive a visible focus outline.

## Routing and base path

`main.tsx` mounts a `BrowserRouter`. Its `basename` is derived from Vite's `import.meta.env.BASE_URL`, so both `/` deployments and configured prefixes such as `/bseu/` use the same route definitions.

Direct browser requests are served by the existing history fallbacks:

- Vite development serves `index.html` for client routes;
- `frontend/nginx.conf` uses `try_files $uri $uri/ /index.html`;
- the production Nginx template strips the configured base prefix and falls back through `__BASE_PATH__index.html`.

The existing Nginx configuration already had the required SPA behavior, so no unrelated deployment changes were necessary.

## Homepage data behavior

The homepage requests `GET /api/catalog/meta` through the shared typed API client. The university count is taken from `counts.universities`; it is not hardcoded. If metadata cannot be loaded or returns an unusable count, the page states that the number could not be confirmed and never replaces it with zero.

The page explicitly says that live monitoring currently works only for BSEU and that incomplete platform coverage is not evidence of real-world absence.

## Preserved monitor behavior

The former root `App` dashboard is mounted as `MonitorPage` at `/monitor`. Its API calls and behavior remain unchanged:

- legacy specialties, latest snapshot, history and collector status reads;
- local score what-if calculation;
- competition, estimated cutoff and position display;
- score distribution and historical charts;
- stale-source and last-correct-snapshot warnings;
- official source links;
- manual refresh using the existing token prompt and endpoint.

No backend API, scheduler, 304 handling, snapshot deduplication or Telegram code is changed by this milestone.

## Tests

Frontend component tests use Vitest, jsdom and React Testing Library:

```powershell
Push-Location frontend
npm run test
npm run lint
npm run typecheck
npm run build
Pop-Location
```

All API responses are supplied by a `fetch` mock. The tests do not import or start FastAPI, APScheduler, Telegram, SQLite, live HTTP sources or production lifespan code. They cover homepage data and failure states, `/monitor`, navigation and active state, keyboard order, the 404 page and one-`h1` page structure.

The repository-wide command also runs the frontend tests before lint and build:

```powershell
.\check.ps1
```

## Deferred milestones

The following remain deferred: `/universities`, search and filters, university/program details, recommendations, authentication, profiles, favorites, comparison, watchlists and Telegram linking.
