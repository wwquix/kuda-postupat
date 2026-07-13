# Контракт адаптеров официальных источников

## Назначение

Адаптер изолирует особенности официального источника конкретного вуза и возвращает нормализованные DTO. Он не открывает SQLAlchemy session, не сохраняет данные, не отправляет Telegram, не формирует FastAPI responses и не вычисляет пользовательские рекомендации.

Первой реализацией станет extraction существующего БГЭУ flow из `backend/app/scraper.py` и `backend/app/parser.py` после создания canonical schema и backfill. Этот документ не добавляет adapter code.

## Capabilities

```python
@dataclass(frozen=True)
class AdapterCapabilities:
    university_profile: bool
    program_catalog: bool
    admission_plan: bool
    current_applications: bool
    score_distribution: bool
    historical_cutoffs: bool
    tuition: bool
    scholarships: bool
    dormitories: bool
    media: bool
```

Capabilities описывают поддерживаемые типы данных, а не их доступность в конкретный момент. `False` означает «адаптер не реализует capability» и запрещает вызов соответствующего метода. `True` не разрешает выдумывать пустой результат: недоступный источник возвращает типизированную ошибку или partial result.

## Общие типы

Ниже приведён дизайн интерфейса; точные Pydantic/dataclass definitions создаются в milestone extraction.

```python
class UniversityAdapter(Protocol):
    university_code: str
    capabilities: AdapterCapabilities

    async def fetch_university_profile(self, request: AdapterRequest) -> AdapterResult[UniversityProfileDTO]: ...
    async def fetch_program_catalog(self, request: AdapterRequest) -> AdapterResult[list[ProgramDTO]]: ...
    async def fetch_admission_state(self, request: AdmissionRequest) -> AdapterResult[list[AdmissionStateDTO]]: ...
    async def fetch_tuition(self, request: AdapterRequest) -> AdapterResult[list[TuitionDTO]]: ...
    async def fetch_scholarships(self, request: AdapterRequest) -> AdapterResult[list[ScholarshipDTO]]: ...
    async def fetch_dormitories(self, request: AdapterRequest) -> AdapterResult[list[DormitoryDTO]]: ...
    async def healthcheck(self, request: HealthcheckRequest) -> AdapterHealthDTO: ...
```

### Request context

`AdapterRequest` содержит:

- `university_code`: стабильный machine code, совпадающий с зарегистрированным adapter;
- `admission_year`: optional для profile/general facts, required для campaign-specific methods;
- `locale`: initially `ru-BY`, не влияет на persisted machine values;
- `conditional`: optional `etag` и `last_modified` для конкретного source URL;
- `checked_after`: optional service hint для freshness, не разрешение вернуть cached persisted entities;
- `request_id`: correlation ID без user secrets;
- `timeout_seconds`: ограниченный core settings;
- `force_full_fetch`: service-controlled recovery after 304 without canonical data.

`AdmissionRequest` дополнительно допускает bounded filters `external_program_codes`, `study_forms`, `funding_types`, но adapter обязан уметь вернуть полный поддерживаемый campaign dataset, если источник публикует его одним документом. Фильтры не должны менять понимание source hash.

`HealthcheckRequest` выполняет минимальную проверку доступности/схемы и не создаёт snapshots.

### Result envelope

```python
@dataclass(frozen=True)
class AdapterResult(Generic[T]):
    status: Literal["available", "partial", "not_modified"]
    data: T | None
    source: SourceMetadata
    warnings: tuple[AdapterWarning, ...]
```

`data` обязательно для `available`, может содержать неполные DTO для `partial` и обязано быть `None` для `not_modified`. Пустой список допустим только если официальный источник явно и успешно сообщил об отсутствии записей; иначе это schema/partial error.

### Source metadata

Каждый result и каждый DTO, если записи происходят из разных документов, несёт:

- `source_url` — точный официальный URL;
- `source_type` — стабильный enum;
- `http_status`;
- `checked_at` — UTC-время завершения успешной проверки;
- `source_updated_at` — nullable время из источника с исходным timezone/precision;
- `etag`, `last_modified` — nullable validators;
- `content_hash` — SHA-256 тела для полученного `200`, nullable для `304`;
- `verification_method` и `confidence`;
- `adapter_version` и `schema_version`;
- `availability` — `available`, `partial`, `unknown`, `stale`, `needs_review`;
- `field_sources` — optional mapping для DTO, составленного из нескольких официальных страниц.

URLs должны происходить из конфигурации/аудированного official-source registry. Адаптер не подставляет фиктивные URL.

## Нормализованные DTO

### UniversityProfileDTO

Стабильные machine fields: code, current short/full name, institution kind, ownership type, city/region, official/admissions URLs, optional description. Nullable facts сопровождаются availability; отсутствие значения не означает отрицание факта.

### ProgramDTO

Представляет академическую программу независимо от формы, funding и year: `external_program_code` nullable, canonical/display name, optional qualification, professions and subject references. Вложенные offering DTO допустимы только как transport convenience; service разделяет их при persistence.

### AdmissionStateDTO

Одна строка соответствует одному будущему `ProgramOffering` и содержит:

- program external code/name;
- admission year, study form, funding type;
- optional plan/deadline;
- current applications and optional score distribution;
- source observation/update timestamps;
- raw row hash and normalized deduplication payload version;
- per-field availability and warnings.

Derived competition/cutoff не являются обязательной частью adapter DTO: service рассчитывает их единообразно. Адаптер не маркирует текущую оценку как official historical cutoff.

### TuitionDTO

Program/offering reference, academic/admission year, currency, amount nullable only with partial status, course number nullable, period/semester, conditions, validity dates and provenance. `0` допустим только если официальный источник прямо публикует нулевую стоимость и это проверено.

### ScholarshipDTO

Machine scholarship type, title, amount/range nullable, currency, eligibility/conditions, validity and provenance.

### DormitoryDTO

Verified dormitory/unit name, address nullable, capacity nullable, availability statement, eligibility/conditions and provenance. «Нет общежития» разрешено только при explicit official statement.

### MediaDTO

Media type, official asset/page URL, optional thumbnail/alt/caption, rights/attribution if published, checksum and provenance. Adapter не копирует third-party images как official.

### AdapterHealthDTO

Source health (`healthy`, `degraded`, `unavailable`, `schema_changed`, `disabled`), checked time, latency, HTTP status nullable, conditional support, schema validation result and sanitised error code. Healthcheck не возвращает secrets или raw response bodies.

## Методы

### `fetch_university_profile(request)`

- **Вход:** code, optional conditional validators and request context; admission year обычно не нужен.
- **Результат:** один normalized profile; field-level provenance для нескольких official pages.
- **Ошибки:** capability unsupported, transport/timeout, HTTP rejection, decode/schema/source identity mismatch.
- **Freshness:** profile TTL задаёт service; adapter всегда возвращает actual `checked_at`.
- **Partial:** разрешён для необязательных description/region details, но canonical identity и официальный source должны быть подтверждены.
- **Fail closed:** несоответствие source identity не обновляет профиль.

### `fetch_program_catalog(request)`

- **Вход:** code, admission year optional/required по природе источника, validators.
- **Результат:** программы с external identity и, при наличии, offering dimensions.
- **Ошибки:** неизвестные обязательные dimensions, duplicate external codes с конфликтующими names, schema change.
- **Freshness/source:** на result и записях; год публикации не заменяет `checked_at`.
- **Partial:** допускаются программы без qualification/professions; строки без program name/external identity отклоняются.
- **Fail closed:** подозрительно пустой ранее непустой каталог требует `needs_review`, а не массовой деактивации.

### `fetch_admission_state(request)`

- **Вход:** обязательный admission year; optional bounded filters; validators.
- **Результат:** список offering observations, включая plan/current applications/distribution в пределах capabilities.
- **Ошибки:** missing required campaign dimensions, malformed counts, inconsistent totals/distribution, source masquerading as historical page.
- **Freshness/source:** observation time, source update time and check time раздельны.
- **Partial:** plan может быть доступен без current applications или distribution; availability указывается отдельно.
- **Fail closed:** отрицательные counts, нераспознаваемая form/funding, отсутствие обязательной схемы или выбранной configured BSEU row не создают snapshot.

### `fetch_tuition(request)`

- **Вход:** code, admission/academic year, optional program filters, validators.
- **Результат:** normalized tuition records by course/period/currency.
- **Ошибки:** amount without currency/period, ambiguous unit, unofficial source.
- **Freshness/source:** validity and source dates отдельны от HTTP check.
- **Partial:** text «уточняется» становится unknown/partial, не нулём.
- **Fail closed:** ambiguous numbers are withheld with warning.

### `fetch_scholarships(request)`

- **Вход:** code, optional academic year and validators.
- **Результат:** scholarship types/amounts/conditions.
- **Ошибки:** source or currency ambiguity, unsupported capability.
- **Freshness/source:** record validity and provenance required.
- **Partial:** conditions-only fact is valid partial data.
- **Fail closed:** no inferred eligibility or amount.

### `fetch_dormitories(request)`

- **Вход:** code and validators.
- **Результат:** verified units/statements and conditions.
- **Ошибки:** source identity mismatch, unsupported capability, schema change.
- **Freshness/source:** checked/verified dates required; capacity date optional.
- **Partial:** existence may be available while capacity/address is unknown.
- **Fail closed:** inability to find information is `unknown`, never `false`.

### `healthcheck(request)`

- **Вход:** code, timeout, request ID; conditional validators optional.
- **Результат:** source health only.
- **Ошибки:** represented as sanitised health state unless programmer/configuration error prevents adapter construction.
- **Freshness:** always contains current `checked_at` for completed check.
- **Side effects:** service may persist source-run health; adapter itself does not write DB.

Media may later receive a dedicated `fetch_media` method even though it is not in the minimum method list; until then `media=True` is invalid unless the adapter exposes the versioned extension. Capabilities and methods must remain consistent.

## Conditional requests and HTTP 304

1. Service loads validators for the exact data source and passes them to adapter.
2. Adapter sends `If-None-Match`/`If-Modified-Since` only to that URL.
3. On 304 with existing accepted canonical data, adapter returns `not_modified`, `data=None`, new `checked_at`, existing validator metadata, and no snapshot. Service updates source check/run state only.
4. On 304 without accepted canonical data, service retries once with `force_full_fetch=True` and no validators. A second 304 is `not_modified_without_data`, a controlled fail-closed error.
5. A 304 never changes `source_updated_at`, content hash, verified time, record values or notification fingerprints.
6. Validators are not shared across URLs, capabilities or universities.

This preserves the tested behavior in `backend/tests/test_scraper_304.py`.

## Error model

Stable categories:

- `unsupported_capability` — programmer/service requested a declared false capability;
- `configuration_error` — missing or invalid audited source config;
- `transport_error` / `timeout` — exhausted bounded retry policy;
- `http_error` — sanitised status and source ID;
- `decode_error` — unsupported/malformed encoding;
- `schema_changed` — required shape missing or inconsistent;
- `source_identity_mismatch` — wrong page/document type;
- `partial_data` — safe subset available with warnings;
- `not_modified_without_data` — recovery fetch failed to provide body;
- `rate_limited` — local/upstream limit.

Exceptions must not contain secret-bearing URLs, authorization headers, cookies or raw HTML/XML. Retryability is explicit. Services record a failed source run and preserve last accepted facts.

## Partial support and fail-closed rules

- Capability truth and field availability are separate.
- Required identity fields failing validation reject the whole result.
- Optional fact failures can produce `partial` with field warnings.
- A source becoming empty, changing schema or changing identity does not delete/deactivate previously accepted data automatically.
- Counts and money are never defaulted to zero; booleans are never inferred from absence.
- Cross-source merging occurs in a service with precedence from `docs/universities-source-audit.md`, not inside a university adapter.
- Parser/raw payload can be retained only according to an explicit storage policy; raw hashes and run metadata are always retained for monitoring dedup/audit.

## Registry

```python
adapter = adapter_registry.get(university_code)
```

Registry requirements:

- registration uses stable university code and one adapter factory/version;
- duplicate code is a startup error;
- unknown code raises typed `AdapterNotRegisteredError`;
- construction receives shared HTTP client factory/settings, never ORM session;
- registry exposes capabilities without triggering network requests;
- tests verify all online/candidate configured adapters have matching canonical university codes;
- disabled adapters remain explicit registry metadata, not silent fallbacks;
- no `if/elif` dispatch by university code in routes, services or scheduler.

The scheduler asks a monitoring service for enabled source jobs; the service resolves the registry and persists results. This keeps adapter selection centralized while orchestration and transactions stay outside adapters.

## BSEU parity requirements

Before routing production BSEU refresh through a new adapter, parity tests must prove:

- official XML URL and Windows-1251 HTML fallback behavior remain supported;
- named XML attributes and `G_*` validation stay fail closed;
- «Экономическая информатика», full-time paid, plan and score 276 monitoring remains identical;
- ETag/Last-Modified and all 304 scenarios preserve current semantics;
- normalized snapshot hash prevents duplicates;
- source/check/snapshot timestamps remain distinguishable;
- scraper runs and content hashes persist;
- old API payloads, `refresh.ps1`, scheduler and owner Telegram notifications remain compatible.

Only then may the compatibility service delegate to the adapter-backed monitoring service.
