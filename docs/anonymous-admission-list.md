# Анонимный список поступления

## Назначение и границы

Milestone `M-MY-LIST-01` реализует первый пользовательский срез раздела 8
roadmap: один анонимный профиль, один личный балл, сохранённые вузы и программы,
а также страницу `/my-list`. Регистрация, синхронизация между устройствами,
сравнение, рекомендации, watchlists, уведомления и Telegram не входят в этот
срез.

Ранний эскиз M8 упоминал signed HttpOnly cookie, public UUID и merge
localStorage. Фактический контракт этого совместимого первого среза уже:
непрозрачный Bearer-токен хранится только на устройстве пользователя, public
UUID отсутствует, автоматического merge нет. Эти возможности не следует
считать реализованными.

## Анонимная идентичность и токен

Профиль создаётся лениво при первом действии, которому требуется сохранение:

1. Backend генерирует `secrets.token_urlsafe(32)`, то есть использует 32 байта
   криптографически стойкой случайности.
2. В SQLite записывается только SHA-256 hash токена.
3. Raw token возвращается только ответом `POST /api/profile` и больше не
   появляется в API-ответах.
4. Frontend сохраняет raw token в versioned key
   `bseu:anonymous-profile-token:v1` в `localStorage`.
5. Только запросы profile API получают заголовок
   `Authorization: Bearer <token>`.

Токен не передаётся в URL и не должен попадать в логи. Если сохранённый токен
невалиден, frontend удаляет его, показывает понятное состояние и создаёт новый
профиль только после следующего явного действия пользователя. Одновременные
первые действия используют один общий запрос создания профиля.

Это локальная анонимная идентичность, а не аккаунт. Очистка browser storage,
смена браузера или устройства приводит к потере доступа к прежнему списку;
механизма восстановления в этом milestone нет.

## Таблицы

Migration `0004_anonymous_admission_list` добавляет ровно три таблицы:

- `anonymous_profiles`: внутренний integer primary key, unique token hash,
  nullable `personal_score`, `created_at`, `updated_at`;
- `saved_universities`: composite primary key из profile и University foreign
  keys, `created_at`;
- `saved_programs`: composite primary key из profile и Program foreign keys,
  `created_at`.

Удаление профиля каскадно удаляет только его связи. University и Program
защищены от удаления через favorite-связь и никогда не удаляются операцией
«Удалить из списка». Composite primary keys гарантируют уникальность пары.

## API

Все ответы со списком детерминированно отсортированы и не содержат internal
profile ID или token hash.

| Метод | Путь | Назначение |
| --- | --- | --- |
| `POST` | `/api/profile` | Создать профиль; единственный ответ с raw token |
| `GET` | `/api/profile` | Получить профиль и полный сохранённый список |
| `PATCH` | `/api/profile/score` | Установить integer score или очистить его через `null` |
| `GET` | `/api/profile/saved` | Получить полный сохранённый список |
| `PUT` | `/api/profile/universities/{slug}` | Идемпотентно сохранить University |
| `DELETE` | `/api/profile/universities/{slug}` | Идемпотентно удалить University из списка |
| `PUT` | `/api/profile/programs/{university_slug}/{program_slug}` | Идемпотентно сохранить принадлежащую вузу Program |
| `DELETE` | `/api/profile/programs/{university_slug}/{program_slug}` | Идемпотентно удалить Program из списка |

Кроме create, каждый endpoint требует Bearer credential. Отсутствующий или
невалидный token возвращает контролируемый `401`, неизвестный вуз или программа
— `404`. Endpoint'ы не запускают scraper, scheduler, refresh или Telegram.

## Личный балл и мониторинг БГЭУ

Баллом считается целое число от 0 до 500 включительно. Одинаковые доменные
границы применяются в конфигурации, Pydantic-схеме и database constraint;
`null` означает, что пользователь не указал балл. Ноль не подставляется по
умолчанию.

Для сохранённой программы live-статус рассчитывается только если её Offering
явно связан с существующим мониторингом БГЭУ, личный балл задан, а сохранённые
данные достаточно свежие и полные. Backend вызывает существующую доменную
функцию `calculate_metrics`; React только отображает возвращённый результат и
не содержит копии формулы.

Если балла нет, интерфейс предлагает его добавить. Неподдерживаемое покрытие
показывается ровно как `Мониторинг пока недоступен`. Ошибка, stale или
недостаточные данные показываются как `Статус временно недоступен`; ни одно из
этих состояний не является прогнозом отказа в поступлении.

## Поведение сохранения и страница

Кнопки сохранения доступны на карточках `/universities`, на странице вуза и на
странице программы. Они остаются на текущем маршруте, имеют состояния
`Сохранить`, `Сохранено`, `Удалить из списка`, блокируются на время запроса и
не удаляют уже показанные данные при ошибке API.

`/my-list` показывает редактор балла, сохранённые вузы и программы, реальные
ссылки на catalog detail routes, существующие Offering summaries и только
server-derived BSEU status. Пустое состояние содержит ссылки на
`/universities` и `/monitor`. Маршрут работает и при прямом открытии под
production base path `/bseu/` через существующий SPA fallback Nginx.

## Приватность

Профиль не собирает имя, email, телефон, местоположение или Telegram identity.
Bearer-токен является credential: любой, кто получил его, получает доступ к
этому анонимному списку. Поэтому его нельзя логировать, передавать через URL или
копировать в telemetry. Этот milestone не предоставляет recovery, revocation,
cross-device sync или управление активными сессиями.

## Сфокусированные проверки

Из корня репозитория:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pytest tests/test_anonymous_profile_api.py tests/test_migrations.py tests/test_calculations.py tests/test_catalog_api.py tests/test_legacy_compatibility.py
..\.venv\Scripts\python.exe -m ruff check app/admission_score.py app/profile_api.py app/profile_models.py app/profile_repository.py app/profile_schemas.py app/profile_security.py app/profile_service.py tests/test_anonymous_profile_api.py tests/test_migrations.py
Pop-Location

Push-Location frontend
npm run test -- AnonymousAdmissionList.test.tsx
npm run lint
npm run typecheck
Pop-Location
```

Полная проверка milestone выполняется через `./check.ps1`, затем
`git diff --check`. Runtime QA выполняется только через `start-dev.ps1`, где
`DEVELOPMENT_SAFE_MODE=true`; `POST /api/refresh` при этой проверке не
вызывается.

## Отложено

Отдельными milestone остаются зарегистрированные аккаунты и восстановление
доступа, рекомендации, сравнение, watchlists, уведомления, Telegram linking и
любая cross-device синхронизация.
