# Public monitor MVP states

`/monitor` is a public read-only view. It reads the existing specialties,
snapshot history, collector status, health and public configuration endpoints.
It never asks for `MANUAL_REFRESH_TOKEN` and never calls `POST /api/refresh`.
The protected operator endpoint and `refresh.ps1` remain unchanged.

## Collector states

The page reports whether automatic updates are enabled, the last successful
check, the next scheduled check and the current collector result. A running
collector is shown as refreshing. `success` means new data were received;
`not_modified` is rendered as «Источник проверен, изменений нет».

A collector failure is a separate alert. If a valid snapshot already exists,
it remains visible. The source timestamp is evaluated independently: an old
BSEU timestamp says only that BSEU has not published newer source data and is
not presented as a collector failure.

If no valid snapshot exists, the page says «Первый корректный снимок конкурсной
ситуации ещё не получен». Its retry repeats public GET reads only.

## Telegram availability

`/my-list` checks `GET /api/config` before loading Telegram link state. When
`telegram_enabled` is `false`, it hides the connection form, does not load link
status or create a challenge, and shows «Telegram-уведомления появятся позже».
Saved items, watches and the event feed continue to work. When the flag is
`true`, the existing linking and delivery behavior is preserved.

## Verification boundary

Component tests cover success, unchanged, refreshing, collector error, stale
source time, no-snapshot retry, scheduler unavailable and disabled Telegram.
Local browser QA uses `start-dev.ps1` safe mode and GET requests only; it must
not trigger a manual refresh or any production startup side effects.
