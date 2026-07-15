# Telegram-уведомления для анонимных наблюдений

## Границы milestone

`M-TELEGRAM-WATCH-01` связывает один анонимный профиль с одним Telegram chat и
доставляет туда новые persisted `program_watch_events`. Зарегистрированные
аккаунты, восстановление доступа, cross-device merge, email/browser push,
Recommendations и дополнительные university adapters не входят в этот срез.

Существующий owner-mode Telegram (`TELEGRAM_ENABLED` + `TELEGRAM_CHAT_ID` и
`notification_logs`) сохранён без изменения семантики. Profile-scoped delivery
использует отдельные link/challenge/delivery таблицы и не записывает chat ID в
`notification_logs`.

## Владение и приватность

- Link принадлежит внутреннему `anonymous_profiles.id`; bearer credential
  профиля не копируется в link, challenge, delivery, Telegram URL или message.
- Один профиль и один Telegram chat могут иметь только по одной активной связи.
  Частичные unique indexes предотвращают активное владение одним chat разными
  профилями.
- Сохраняется только технически необходимый chat ID. Username, имя, телефон и
  история сообщений не сохраняются и не возвращаются публичным API.
- Unlink помечает связь неактивной и сохраняет исторический delivery status.
  `ProgramWatchEvent`, Snapshot и Program при этом не удаляются.
- Удаление анонимного профиля следует существующему `CASCADE` для его links,
  challenges, watches, events и delivery records; catalog и snapshots остаются.

## Одноразовый challenge

`POST /api/profile/telegram/challenge` требует действующий profile bearer token.
Backend генерирует `secrets.token_urlsafe(24)` (192 бита случайности), хранит
только SHA-256 hash и устанавливает expiry ровно через 15 минут. Новый challenge
помечает использованными предыдущие неиспользованные challenges этого профиля.

Raw link token возвращается только внутри `deep_link` creation response:

```text
https://t.me/<bot-username>?start=<one-time-link-token>
```

Он не является profile bearer token. Status API возвращает только expiry, но не
восстанавливает raw token. Поэтому после перезагрузки UI создаёт новую ссылку,
если пользователю снова нужно открыть Telegram.

Challenge одноразовый. Invalid, expired, consumed и replayed token не создаёт и
не переносит link. Повторное связывание того же профиля с тем же chat
идемпотентно; попытка присвоить chat другого профиля отклоняется без раскрытия
владельца.

## API и webhook

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/api/profile/telegram` | Active link status и текущий challenge expiry |
| `POST` | `/api/profile/telegram/challenge` | Заменить challenge и один раз получить deep link |
| `DELETE` | `/api/profile/telegram` | Идемпотентно отключить Telegram текущего профиля |
| `POST` | `/api/telegram/webhook` | Принять Telegram update для `/start <token>` |

Profile endpoints используют обычный `Authorization: Bearer ...`. Webhook
использует стандартный header Telegram
`X-Telegram-Bot-Api-Secret-Token`. Отсутствующий, пустой или неверный secret
получает `401`; secret не размещается в route URL. Обрабатываются только поля
`message.chat.id` и `message.text`, необходимые для `/start <token>`.
Unsupported update безопасно отвечает `ignored`, а internal exception, token и
chat ID не попадают в ответ.

После успешного link бот отправляет безопасное подтверждение. Ошибка этой
отправки не отменяет уже подтверждённое владение link и не раскрывает Telegram
response.

## Доставка WatchEvent

Один integration point находится после commit monitoring результата и после
успешного `evaluate_program_watches`. Scheduled refresh и authenticated manual
refresh используют общий `refresh_bseu -> AdmissionScraper.refresh("bseu")`
путь, поэтому доходят до одного delivery service.

Доставка читает только сохранённые public значения `ProgramWatchEvent`, Program
и University. Message содержит название программы, вуза, готовое описание
изменения и event time. Ссылка на Program добавляется только при валидном
`PUBLIC_APP_BASE_URL`.

Для пары `(watch_event, profile_link)` существует не больше одной application
delivery record. Попытка фиксируется отдельной транзакцией до HTTP-вызова;
confirmed result фиксируется следующей отдельной транзакцией. Failure не
откатывает Snapshot, ScraperRun или WatchEvent.

Состояния:

- `pending` — попытка начата, но confirmed result ещё не записан;
- `retryable` — получен известный retryable transport/429/5xx failure;
- `failed` — permanent rejection либо исчерпан лимит;
- `confirmed` — Telegram API вернул успешный HTTP result.

Retryable failure допускает максимум три application attempts. Permanent
4xx/rejected request автоматически не повторяется. Confirmed delivery никогда
не отправляется повторно. Error summary — bounded operational code до 200
символов, без response body, URL, token, stack trace или chat ID.

Это не обещание strict exactly-once: при сетевом обрыве после фактического
принятия Telegram API результат неоднозначен, и bounded retry теоретически может
дать duplicate message. Такой случай остаётся failure/pending до подтверждённого
HTTP success и никогда не показывается пользователю как «Отправлено».

## Конфигурация

```env
# legacy owner mode
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# anonymous profile linking and watch delivery
TELEGRAM_BOT_USERNAME=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_WATCH_DELIVERY_ENABLED=false
PUBLIC_APP_BASE_URL=
```

`TELEGRAM_WATCH_DELIVERY_ENABLED` по умолчанию `false`. При `true` startup
configuration требует bot token, bot username и отдельный webhook secret.
`PUBLIC_APP_BASE_URL` опционален, но при наличии должен быть абсолютным HTTP(S)
URL без query/fragment. Secret values находятся только в `.env` или production
EnvironmentFile и не выдаются health/config API.

`DEVELOPMENT_SAFE_MODE=true` по-прежнему отключает scheduler и startup refresh.
Кроме того, link confirmation и WatchEvent delivery не выполняют реальных
Telegram HTTP requests в этом режиме, даже если delivery flag включён.

## Production registration

Существующий Nginx `location ^~ <base>/api/` уже проксирует webhook в FastAPI;
secret header передаётся без отдельного location. После deployment, migrations,
HTTPS и заполнения production EnvironmentFile оператор регистрирует webhook
через официальный Telegram `setWebhook` API. Не выполняйте регистрацию в этом
milestone и не помещайте реальные значения в shell history.

Параметры запроса:

```text
POST https://api.telegram.org/bot<bot-token>/setWebhook
url=https://<public-host>/<base-path>/api/telegram/webhook
secret_token=<telegram-webhook-secret>
allowed_updates=["message"]
```

Используйте secret-reading механизм оператора или temporary protected script,
а не literal secrets в командной строке. Проверяйте только sanitised API result;
не печатайте URL Telegram API с bot token.

## `/my-list`

Секция `Уведомления в Telegram` имеет отдельные loading, not-linked, challenge
creation, active challenge, expired, linked, unlink confirmation и retryable
error states. Link открывается в новом tab с `noopener noreferrer`; profile
token и chat ID не попадают в browser URL. Status обновляется без reload.
Unlink требует явного keyboard-accessible подтверждения и не меняет enabled
state Program watches.

Watch history показывает `Отправлено в Telegram` только при delivery state
`confirmed`. Pending, retryable и failed не называются отправленными.

## Проверка

Из корня репозитория:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pytest `
  tests/test_telegram_watch_notifications.py `
  tests/test_program_watchlist.py `
  tests/test_monitoring_adapter_registry.py `
  tests/test_telegram.py tests/test_config.py tests/test_migrations.py
Pop-Location

Push-Location frontend
npm run test -- AnonymousAdmissionList.test.tsx
npm run lint
npm run typecheck
Pop-Location

.\check.ps1
git diff --check
```

Tests используют temporary SQLite, mocked Telegram transport и mocked webhook
updates. Default suite не регистрирует webhook, не соединяется с Telegram и не
пишет link/delivery data в main SQLite.

## Отложено

Отдельными milestone остаются registered accounts, recovery и cross-device
linking/merge, Recommendations, comparison, email/browser notifications,
дополнительные monitoring adapters и production rehearsal.
