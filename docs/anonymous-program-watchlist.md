# Анонимное наблюдение за программой БГЭУ

## Назначение и границы

Milestone `M-WATCHLIST-01` реализует первый пользовательский срез раздела 9
roadmap: владелец существующего анонимного профиля может включить наблюдение за
сохранённой Program БГЭУ и увидеть внутри `/my-list` историю значимых изменений.

Срез не добавляет регистрацию, cross-device merge, сравнение, рекомендации,
другие вузы, Telegram linking или доставку. Существующая owner-mode отправка
Telegram остаётся совместимой, но новые profile-scoped события никуда внешне не
отправляются.

## Владение и поддерживаемая область

Watch принадлежит `anonymous_profiles.id`; raw bearer token в watch/event
таблицы не записывается. Все watch endpoints используют существующий
`Authorization: Bearer <profile token>` и возвращают только данные текущего
профиля.

В этом milestone поддерживается только сохранённая Program БГЭУ, у которой есть:

- каноническая `ProgramOffering` с `monitoring_supported=true` и status `online`;
- реальная `LegacySpecialtyMapping` к текущему BSEU monitoring flow;
- registry-backed BSEU adapter как единственный operational adapter.

Отсутствующая University/Program или несовпадающий path возвращает `404`.
Попытка наблюдать несохранённую либо неподдерживаемую Program возвращает
контролируемый `409`; scraper при этом не запускается.

## Migration и таблицы

Revision `0005_anonymous_program_watchlist` добавляет две таблицы и не меняет
существующие записи:

- `program_watches`: FK на anonymous profile с `CASCADE`, FK на Program с
  `RESTRICT`, флаг `enabled`, nullable baseline
  `last_evaluated_snapshot_id`, timestamps и unique `(profile_id, program_id)`;
- `program_watch_events`: FK на watch с `CASCADE`, FK на source
  `AdmissionSnapshot` с `RESTRICT`, stable `event_kind`, JSON previous/current
  public values, `created_at` и unique
  `(watch_id, source_snapshot_id, event_kind)`.

API «отключить» деактивирует watch и сохраняет его события. Удаление анонимного
профиля каскадно удаляет только принадлежащие ему watches/events. Program,
Offering, Snapshot и другие monitoring данные не удаляются.

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/api/profile/watches` | Активные watches текущего профиля |
| `PUT` | `/api/profile/watches/{university_slug}/{program_slug}` | Идемпотентно включить наблюдение |
| `DELETE` | `/api/profile/watches/{university_slug}/{program_slug}` | Идемпотентно отключить наблюдение |
| `GET` | `/api/profile/watch-events` | Детерминированный feed, новые события первыми |

Ответы не содержат profile/watch/snapshot integer IDs, token hash или raw event
JSON. Feed отдаёт stable event kind, server-formatted описание, время и public
Program/University identity. Ни один endpoint не выполняет HTTP-запрос к БГЭУ,
refresh или Telegram.

## Evaluation point, baseline и deduplication

`AdmissionScraper.refresh("bseu")` сначала завершает parse/calculation,
Snapshot dedup, source health и успешный `ScraperRun`, затем commit'ит этот
monitoring результат. Только после commit отдельный `evaluate_program_watches`
получает ID реально созданных Snapshot.

- `304`, unchanged payload, parser/transport failure и update без нового Snapshot
  evaluator не вызывают;
- stale latest Snapshot не становится baseline и не создаёт event;
- первое включение фиксирует последний usable persisted Snapshot как baseline;
- если Snapshot ещё нет, первый будущий usable Snapshot только устанавливает
  baseline без ложного события;
- после evaluation `last_evaluated_snapshot_id` двигается атомарно вместе с
  events;
- повторная evaluation того же Snapshot ничего не создаёт; это дополнительно
  защищено database unique constraint;
- re-enable после паузы начинает новый baseline с текущего usable Snapshot и не
  выдаёт изменения за отключённый период;
- exception evaluator откатывает только watch transaction, логируется и не
  отменяет уже committed Snapshot/ScraperRun.

Scheduled refresh и ручной `POST /api/refresh` входят в один `refresh_bseu` →
`AdmissionScraper.refresh("bseu")` путь, поэтому используют один evaluator.

## Реализованные event kinds

- `applications_total_changed` — изменилось persisted число заявлений;
- `estimated_cutoff_changed` — изменился persisted предполагаемый диапазон либо
  честное состояние «конкурс пока отсутствует»;
- `user_position_changed` — изменилось примерное место для текущего profile score;
- `user_status_changed` — изменился существующий `calculate_metrics().status` для
  текущего profile score.

Score-dependent значения для предыдущего и текущего Snapshot вычисляются одной
существующей доменной функцией `calculate_metrics`; формула не дублируется в
watch service или React. При `personal_score=null` создаются только общие events.
Если один из сравниваемых расчётов сообщает `Недостаточно данных`, score-dependent
event не создаётся.

Отдельный event «вошёл/вышел из диапазона поступления» пока не реализован:
доменная модель не содержит отдельного канонического boolean, а выводить его из
русских status labels значило бы создать вторую admission-status семантику.
Изменение реального domain status уже покрывается `user_status_changed`.

## `/my-list`

Каждая сохранённая Program показывает server-derived поддержку и одну из
доступных операций: `Включить наблюдение`, `Наблюдение включено`,
`Отключить наблюдение`. UI не включает watch оптимистично, блокирует кнопку на
время запроса и оставляет retryable error рядом с control.

Секция `История изменений` показывает новые события первыми: Program,
University, event time, готовое описание из сохранённых event values, ссылку на
Program и `/monitor`. Пустое состояние — `Изменений пока нет`, unsupported —
`Мониторинг пока недоступен`. Без личного балла страница явно объясняет, что
position/status events требуют его; ноль не подставляется.

ProfileProvider загружает saved list, active watches и event feed вместе. При
невалидном local token применяется существующее восстановление: token удаляется,
новый профиль создаётся только следующим явным действием.

## Проверка

Сфокусированные команды из корня:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pytest `
  tests/test_program_watchlist.py `
  tests/test_monitoring_adapter_registry.py `
  tests/test_scraper_304.py `
  tests/test_anonymous_profile_api.py `
  tests/test_migrations.py
Pop-Location

Push-Location frontend
npm run test -- AnonymousAdmissionList.test.tsx
npm run lint
npm run typecheck
Pop-Location
```

Полный gate — `./check.ps1`, затем `git diff --check`. Alembic отдельно
проверяется upgrade с `0004_anonymous_admission_list` на изолированной SQLite.
Runtime QA использует отдельную QA database и `DEVELOPMENT_SAFE_MODE=true`; main
SQLite и live Telegram не используются.

## Следующий milestone

Persisted `program_watch_events` — вход для следующего M9 slice: безопасного
Telegram linking и per-profile delivery с отдельным delivery status/retry и
сохранением owner-mode compatibility. Доставка намеренно не входит в этот
milestone, чтобы сначала зафиксировать ownership, честную event семантику и
deduplication без внешних side effects.
