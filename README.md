# Монитор вступительной кампании БГЭУ
<img width="1903" height="735" alt="image" src="https://github.com/user-attachments/assets/9ead7596-4869-4ad3-8464-a51325fd38e7" />

Сервис получает текущие сведения о поданных документах БГЭУ, хранит историю изменений в SQLite, рассчитывает оценочный текущий порог и показывает dashboard. Публичный `/recommendations` подбирает University и импортированные Program по явным параметрам, не выдавая catalog match за вероятность поступления. Анонимный пользователь может сохранить Program, включить наблюдение и читать персональный feed изменений в `/my-list`. Связать один Telegram chat можно только когда Telegram включён в публичной конфигурации; иначе интерфейс честно сообщает, что уведомления появятся позже. Существующая owner-mode отправка Telegram остаётся отдельной.

> Это автоматическая оценка на основании текущих заявлений, а не официальный итоговый проходной балл. Она не гарантирует поступление.

Источник данных — UTF-8 XML `https://bseu.by/abiturient/xml/1.xml`. Стартовая HTML-страница использует Windows-1251 и загружает этот XML обычным HTTP-запросом; браузерная автоматизация не требуется. Результаты исследования находятся в `docs/source-analysis.md`.

## Быстрый запуск на Windows

Требуются Windows 11, PowerShell 7, Python 3.12+ и Node.js 22+.

```powershell
Set-Location 'C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor'
.\setup.ps1
.\start-dev.ps1
```

Главная страница: `http://127.0.0.1:5173/`

Каталог вузов: `http://127.0.0.1:5173/universities`
<img width="1906" height="941" alt="image" src="https://github.com/user-attachments/assets/827b1a35-ac60-49ce-bf4b-1cc806219cad" />

Подбор вариантов: `http://127.0.0.1:5173/recommendations`
<img width="1900" height="940" alt="image" src="https://github.com/user-attachments/assets/337ec36f-ef62-420e-a535-8cdc5e267d17" />

Страница вуза: `http://127.0.0.1:5173/universities/bseu`

Страница программы: `http://127.0.0.1:5173/universities/bseu/programs/economic-informatics`

Анонимный список поступления и наблюдения: `http://127.0.0.1:5173/my-list`

Монитор поступления БГЭУ: `http://127.0.0.1:5173/monitor`
<img width="1896" height="941" alt="image" src="https://github.com/user-attachments/assets/611f43a5-f17b-4573-bec9-df2300f61875" />

Публичный монитор работает только на чтение: показывает состояние автоматического
сборщика и выполняет безопасные GET-повторы. Он не запрашивает
`MANUAL_REFRESH_TOKEN` и не вызывает защищённое ручное обновление.

Backend API: `http://127.0.0.1:8000`

OpenAPI: `http://127.0.0.1:8000/docs`

`start-dev.ps1` запускает backend с process-only настройкой `DEVELOPMENT_SAFE_MODE=true`:
APScheduler, автоматический startup refresh и связанная с ним фоновая отправка
Telegram в этой development-сессии отключены. `.env` при этом не изменяется.
Подробный контракт и проверка нулевых side effects описаны в
`docs/development-startup.md`.

`setup.ps1` создаёт `.venv`, устанавливает Python/Node зависимости и, только если `.env` отсутствует, копирует `.env.example` и генерирует случайный `MANUAL_REFRESH_TOKEN`. Значение token не печатается. Существующий `.env` никогда не перезаписывается.

Локально допускается Python новее 3.12 с предупреждением. Production unit использует системный `python3` Ubuntu 24.04.

## Первый запуск

```powershell
Set-Location 'C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor'
.\setup.ps1
.\start-dev.ps1
```

`setup.ps1` явно применяет Alembic migrations к новой или уже versioned SQLite. FastAPI больше не создаёт таблицы через `create_all` и не запускает migrations при старте: при отстающей схеме backend завершается с понятной ошибкой до запуска scheduler и HTTP refresh.

Для существующей unversioned legacy-базы setup намеренно отказывается автоматически ставить stamp. Сначала создайте и проверьте backup, затем выполните процедуру из раздела «Alembic migrations» ниже.

При обычном backend startup с production-default `DEVELOPMENT_SAFE_MODE=false`
первый запуск выполняет live refresh. `start-dev.ps1` явно переопределяет режим
только для локального browser QA и не запускает этот refresh. Уже сохранённые
данные остаются доступны; фиктивные значения не подставляются.

## Последующие запуски

```powershell
.\start-dev.ps1
```

PID хранятся в `.runtime`. Повторный запуск проверяет принадлежность PID этому
проекту и не создаёт вторые backend или frontend. Scheduler в safe development
mode не запускается вообще.

Каждый новый backend-процесс из `start-dev.ps1` наследует
`DEVELOPMENT_SAFE_MODE=true`; после запуска скрипт восстанавливает прежнее
значение переменной в вызывающей PowerShell-сессии.

## Остановка

```powershell
.\stop-dev.ps1
```

Скрипт останавливает только подтверждённые деревья процессов этого проекта. Устаревшие PID-файлы удаляются; чужие Python/Node процессы не затрагиваются.

## Ручное обновление

```powershell
.\refresh.ps1
```

Token читается из `.env` и не выводится. Upstream-запросы разрешены не чаще одного раза в пять минут; при более частом вызове скрипт возвращает понятную ошибку.

Прямой API-вызов:

```powershell
$token = ((Get-Content .env | Where-Object { $_ -match '^MANUAL_REFRESH_TOKEN=' }) -split '=', 2)[1]
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/refresh' -Headers @{ 'X-Refresh-Token' = $token }
Remove-Variable token
```

## Запуск проверок

```powershell
.\check.ps1
```

Последовательно выполняются обычные pytest-тесты, отдельный live test, Ruff, изолированные frontend component tests, ESLint, TypeScript и Vite production build. Первая ошибка завершает скрипт с ненулевым кодом.

Отдельные команды:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m pytest -m live -o addopts=
..\.venv\Scripts\python.exe -m ruff check .

Set-Location ..\frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

## Где находится SQLite

Локально:

```text
backend/data/admission.db
```

Production:

```text
/var/lib/bseu-admission-monitor/admission.db
```

Файл БД, WAL/SHM, `.env`, `.venv`, `node_modules`, `.runtime`, логи и frontend build исключены из Git.

## Alembic migrations

Production-схема изменяется только явными Alembic-командами. Запускайте их из корня репозитория; `alembic.ini` и settings независимо от текущего каталога разрешают относительный SQLite URL в `backend/data/admission.db`.

```powershell
# текущая revision
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current

# история и единственный head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini history
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini heads

# применить migrations
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head

# откатить только guarded BSEU backfill на тестовой копии
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini downgrade 0002_core_catalog_schema

# проверить канонические BSEU-связи после upgrade
Push-Location backend
..\.venv\Scripts\python.exe -m app.cli verify-bseu-backfill
Pop-Location
```

Для первой регистрации существующей legacy-базы:

```powershell
# 1. Остановить процессы и создать проверенный SQLite backup.
.\stop-dev.ps1

# 2. Проверить точное соответствие legacy schema.
Push-Location backend
..\.venv\Scripts\python.exe -m app.schema verify-legacy
Pop-Location

# 3. Только после успешной проверки поставить baseline stamp и применить catalog revision.
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini stamp 0001_legacy_baseline
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

Baseline downgrade является no-op и не удаляет legacy history. Revision `0002` удаляет только пустые catalog tables. Guarded downgrade revision `0003` удаляет только точные migration-owned BSEU seed/link rows и сохраняет legacy history; оба downgrade проверяются исключительно на копиях.

> Downgrade production database выполняется только после backup и проверки на копии.

## Импорт канонического каталога вузов

Импорт 47 подтверждённых вузов выполняется явной CLI-командой после `alembic upgrade head`. FastAPI startup, scheduler и обычный refresh никогда не запускают seed автоматически. Источник по умолчанию — versioned-файл `backend/data/research/universities-canonical-2026.json`; сетевые запросы во время seed отсутствуют.

Все catalog-команды запускаются из `backend`, чтобы package `app` разрешался одинаково на Windows и Linux:

```powershell
Push-Location backend

# Проверить canonical research и показать план без записи в SQLite.
..\.venv\Scripts\python.exe scripts\validate_university_research.py
..\.venv\Scripts\python.exe -m app.cli seed-universities --dry-run

# Выполнить одну транзакционную загрузку и проверить результат.
..\.venv\Scripts\python.exe -m app.cli seed-universities
..\.venv\Scripts\python.exe -m app.cli audit-catalog

Pop-Location
```

Повторный `seed-universities` идемпотентен. `University.code` является основным business key, slug проверяется на конфликт. Импорт не удаляет отсутствующие записи, не стирает непустые значения входным `null`, не меняет более свежие `data_verified_at` значения и не делает новые вузы `online`. Категории и официальные registry/site/admissions sources добавляются без удаления вручную созданных связей. Research `review_items`, notes, availability/automation assessment и HTTP-наблюдения остаются в research JSON.

### Аудит каталога

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m app.cli audit-catalog
Pop-Location
```

Exit code 0 означает отсутствие ошибок целостности. Отсутствующие admissions URL, программы или adapters выводятся как warnings и не заменяются выдуманными значениями.

### Экспорт одного вуза

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m app.cli export-university bseu
Pop-Location
```

Команда выводит стабильный JSON, который проходит `backend/data/schemas/university-import.schema.json`. В export входят University, категории, безопасная provenance, DataSources и read-only Program/Offering; ETag, Last-Modified, runtime health errors, legacy snapshots, Telegram и secrets не экспортируются.

### Импорт одного проверенного вуза

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m app.cli import-university .\verified-university.json --dry-run
..\.venv\Scripts\python.exe -m app.cli import-university .\verified-university.json
Pop-Location
```

Файл обязан пройти single-university Schema. Команда применяет ту же merge policy и транзакцию, что canonical seed. Program/Offering в export являются read-only assertions: команда проверяет их совпадение с существующим каталогом, но не создаёт и не изменяет их из произвольного JSON.

### Rollback/restore импорта

Catalog seed не меняет Alembic revision и не удаляет legacy-данные. Для полного локального rollback восстановите проверенный pre-import SQLite backup только при остановленных процессах:

```powershell
.\stop-dev.ps1
$backup = 'backups\admission-before-university-catalog-import-<timestamp>.db'
Get-FileHash -Algorithm SHA256 $backup
Copy-Item -LiteralPath $backup -Destination 'backend\data\admission.db' -Force
```

Перед запуском проверьте `PRAGMA integrity_check`, `PRAGMA foreign_key_check` и Alembic revision восстановленной копии. Restore откатывает также любые runtime snapshots/runs, появившиеся после backup, поэтому production restore требует отдельного согласованного окна и rehearsal на копии.

## Как изменить специальность

Измените `.env` и перезапустите backend:

```env
TARGET_SPECIALTIES=Экономическая информатика
STUDY_FORM=дневная
FUNDING_TYPE=платная
```

Несколько специальностей разделяются `|`:

```env
TARGET_SPECIALTIES=Экономическая информатика|Маркетинг
```

Названия должны существовать для выбранной формы и основы в текущем XML.

## Как изменить балл пользователя

```env
USER_SCORE=276
```

После изменения перезапустите backend. Поле балла в dashboard — локальный what-if сценарий и не меняет серверную историю или Telegram-настройку.

## Как включить Telegram

### Legacy owner-mode

При `TELEGRAM_ENABLED=false` пустой token безопасен и не мешает запуску. При `true` без token/chat ID конфигурация завершается понятной ошибкой до старта приложения.

На production откройте защищённый environment-файл:

```bash
sudo nano /etc/bseu-admission-monitor.env
sudo systemctl restart bseu-admission-monitor
sudo journalctl -u bseu-admission-monitor -n 100 --no-pager
```

Добавьте вручную:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<secret>
TELEGRAM_CHAT_ID=1157476891
```

Bot token нельзя добавлять в Git, README, frontend, shell-аргументы или отчёты. Telegram HTTP-ошибки преобразуются в sanitised-сообщение без URL/token. Дедупликация хранится в SQLite.

### Анонимные Program watches

Profile-scoped Telegram linking и delivery выключены по умолчанию. Для production
заполните защищённый EnvironmentFile и примените migration `0006`:

```env
TELEGRAM_BOT_TOKEN=<secret>
TELEGRAM_BOT_USERNAME=<bot-username-without-at-sign>
TELEGRAM_WEBHOOK_SECRET=<dedicated-secret>
TELEGRAM_WATCH_DELIVERY_ENABLED=true
PUBLIC_APP_BASE_URL=https://<public-host>/bseu/
```

Webhook endpoint — `/api/telegram/webhook`; он требует стандартный header
`X-Telegram-Bot-Api-Secret-Token`. Реальный webhook не регистрируется при setup,
startup или migrations. Полная privacy, retry/dedup, registration и test
процедура описана в `docs/telegram-watch-notifications.md`.

## Production-деплой на Ubuntu 24.04 без Docker

Основной production-режим рассчитан на VPS примерно с 1 vCPU и 2 GB RAM:

- `/opt/bseu-admission-monitor` — код и `.venv`;
- `/etc/bseu-admission-monitor.env` — environment, mode `600`;
- `/var/lib/bseu-admission-monitor/admission.db` — SQLite;
- `bseu-admission-monitor` — systemd service, один Uvicorn worker;
- `127.0.0.1:8091` — backend по умолчанию;
- Nginx — статический `frontend/dist` и proxy `/api/`.

Сначала подключитесь и выполните read-only preflight:

```bash
ssh root@89.169.55.49
systemctl --type=service --state=running
ss -tulpn
nginx -T
df -h
free -h
docker ps
```

Не продолжайте, пока не подтверждены свободный localhost port и отдельный `server_name` либо безопасный URL-префикс. Не занимайте корень существующего сайта и не изменяйте VPN, `kbju-bot` или `fenya-stream-lab`.

С Windows подготовьте архив без секретов и runtime-файлов:

```powershell
tar --exclude=.git --exclude=.env --exclude=.venv --exclude=.runtime --exclude=node_modules --exclude=dist --exclude=backend/data -czf bseu-admission-monitor.tgz .
scp .\bseu-admission-monitor.tgz root@89.169.55.49:/tmp/
```

На сервере:

```bash
rm -rf /tmp/bseu-admission-monitor-release
mkdir -p /tmp/bseu-admission-monitor-release
tar -xzf /tmp/bseu-admission-monitor.tgz -C /tmp/bseu-admission-monitor-release
cd /tmp/bseu-admission-monitor-release
```

После изучения `nginx -T` выберите отдельный host. Пример команды установки, где значения должны соответствовать фактическому preflight:

```bash
BSEU_SERVER_NAME='<dedicated-host>' BSEU_BACKEND_PORT=8091 BSEU_BASE_PATH='/' bash deploy/install-server.sh
```

Скрипт повторно печатает сервисы, порты, Nginx, диск и память; отказывается занимать занятый port и перезаписывать существующую BSEU-конфигурацию. Nginx перезагружается только после успешного `nginx -t`. Telegram остаётся выключенным.

Для URL-префикса соберите frontend с тем же значением:

```bash
BSEU_BASE_PATH='/bseu/'
```

Vite API URLs и assets учитывают `VITE_BASE_PATH`. Окончательный host/path выбирается только после проверки реального `nginx -T`.

## Обновление production

Загрузите новый безопасный архив в новый staging-каталог, затем:

```bash
cd /tmp/bseu-admission-monitor-release
BSEU_BACKEND_PORT=8091 BSEU_BASE_PATH='/' bash deploy/update-server.sh
```

Скрипт останавливает service, создаёт и проверяет отдельный SQLite backup в `/var/backups/bseu-admission-monitor`, затем устанавливает зависимости, проверяет/stamp legacy baseline при первом переходе, выполняет `alembic upgrade head`, запускает service и healthcheck. Перед копированием кода также создаётся timestamped rollback-копия в `/opt/bseu-admission-monitor-rollbacks`. Environment и SQLite находятся вне каталога кода и не перезаписываются.

## Rollback

`rollback-server.sh` откатывает **только код и frontend build**. Он не восстанавливает SQLite и не выполняет Alembic downgrade. `update-server.sh` печатает отдельный paired backup вида `/var/backups/bseu-admission-monitor/admission-before-update-<timestamp>.db`; сохраните этот путь вместе с code checkpoint.

Последняя копия:

```bash
sudo /opt/bseu-admission-monitor/deploy/rollback-server.sh
```

Конкретная копия:

```bash
sudo /opt/bseu-admission-monitor/deploy/rollback-server.sh /opt/bseu-admission-monitor-rollbacks/<timestamp>
```

Если старая версия приложения несовместима с текущей revision, не запускайте её поверх более новой БД. Database restore/downgrade выполняется только при остановленном service, после `integrity_check`/`foreign_key_check` и репетиции на копии; обычный code rollback SQLite не трогает.

## Просмотр логов

Backend и scheduler:

```bash
sudo journalctl -u bseu-admission-monitor -n 100 --no-pager
sudo journalctl -u bseu-admission-monitor -f
```

Nginx:

```bash
sudo tail -n 100 /var/log/nginx/bseu-admission-monitor.access.log
sudo tail -n 100 /var/log/nginx/bseu-admission-monitor.error.log
```

Локальные development-логи находятся в `.runtime/*.log`.

## Backup SQLite

Создание консистентной online-копии:

```bash
sudo install -d -m 0700 /var/backups/bseu-admission-monitor
sudo sqlite3 /var/lib/bseu-admission-monitor/admission.db ".backup '/var/backups/bseu-admission-monitor/admission-$(date -u +%Y%m%dT%H%M%SZ).db'"
sudo chmod 600 /var/backups/bseu-admission-monitor/*.db
```

## Восстановление SQLite

```bash
sudo systemctl stop bseu-admission-monitor
sudo cp /var/backups/bseu-admission-monitor/<backup>.db /var/lib/bseu-admission-monitor/admission.db
sudo chown bseu-admission:bseu-admission /var/lib/bseu-admission-monitor/admission.db
sudo chmod 600 /var/lib/bseu-admission-monitor/admission.db
sudo systemctl start bseu-admission-monitor
sudo /opt/bseu-admission-monitor/deploy/healthcheck.sh
```

## Что делать при изменении XML БГЭУ

1. Проверьте `/api/status` и `journalctl`.
2. Сохраните новый raw response как fixture, не меняйте селекторы вслепую.
3. Убедитесь, что источник всё ещё является текущими сведениями о заявлениях, а не историческими проходными баллами.
4. Обновите именованные атрибуты/aliases парсера и тесты.
5. Запустите `.\check.ps1` и отдельный live test.

При пустом документе, отсутствии `DATAPACKET/ROW`, обязательных полей или `G_*` parser завершает run с ошибкой. Последний корректный snapshot остаётся доступен, dashboard показывает его возраст.

## Ограничения расчёта проходного балла

БГЭУ публикует интервалы баллов. Сервис сортирует диапазоны сверху вниз и находит диапазон, где накопленное число заявлений достигает плана. Точное число внутри диапазона не придумывается.

Если заявлений не больше мест, показывается «Конкурс пока отсутствует — заявлений не больше плана». Предполагаемое место равно числу абитуриентов в диапазонах строго выше пользовательского балла плюс один; порядок внутри одного диапазона неизвестен.

Расчёт не учитывает будущие заявления, приоритеты, оригиналы документов, льготы, целевое поступление и будущие перемещения между специальностями.

## API

- `GET /api/recommendations` — публичный детерминированный подбор Program и University с отдельными monitored, parameter-match и insufficient-coverage состояниями
- `GET /api/universities` — каталог, поиск, фильтры, сортировка и пагинация
- `GET /api/universities/{slug}` — карточка вуза, безопасные источники и импортированные Program/Offering summaries
- `GET /api/universities/{slug}/programs` — импортированные программы вуза
- `GET /api/universities/{university_slug}/programs/{program_slug}` — одна импортированная программа, принадлежащая указанному вузу
- `GET /api/programs` и `GET /api/programs/{id}` — общий каталог программ
- `GET /api/catalog/meta` — значения фильтров и database-derived счётчики
- `GET /api/catalog/health` — локальная целостность каталога без внешних запросов
- `POST /api/profile` — лениво создать анонимный профиль и один раз получить raw token
- `GET /api/profile`, `PATCH /api/profile/score`, `GET /api/profile/saved` — читать список и управлять личным баллом через `Authorization: Bearer ...`
- `PUT`/`DELETE /api/profile/universities/{slug}` — сохранить или удалить вуз
- `PUT`/`DELETE /api/profile/programs/{university_slug}/{program_slug}` — сохранить или удалить программу
- `GET /api/profile/watches`, `PUT`/`DELETE /api/profile/watches/{university_slug}/{program_slug}` — читать и переключать наблюдение за сохранённой BSEU Program
- `GET /api/profile/watch-events` — читать profile-scoped историю значимых изменений
- `GET /api/profile/telegram` — читать безопасный status Telegram link
- `POST /api/profile/telegram/challenge` — создать 15-минутный одноразовый deep link
- `DELETE /api/profile/telegram` — идемпотентно отключить Telegram текущего профиля
- `POST /api/telegram/webhook` — authenticated inbound `/start <link-token>` update
- `GET /api/health`
- `GET /api/config` — только публичная конфигурация, без secret values
- `GET /api/status`
- `GET /api/specialties`
- `GET /api/specialties/{id}/latest`
- `GET /api/specialties/{id}/history`
- `GET /api/specialties/{id}/score-distribution`
- `POST /api/refresh` — `X-Refresh-Token` или `Authorization: Bearer ...`

Полный контракт catalog/search API, включая обязательную пагинацию и семантику неполного покрытия, описан в `docs/catalog-search-api.md`.
Контракт честного подбора, классы результата, ranking и ограничения описаны в `docs/recommendations-v1.md`.
Контракт анонимной идентичности, хранения token и `/my-list` описан в `docs/anonymous-admission-list.md`.
Контракт BSEU Program watches, baseline, event kinds и in-app feed описан в `docs/anonymous-program-watchlist.md`.
Контракт Telegram linking, webhook authentication и WatchEvent delivery описан в `docs/telegram-watch-notifications.md`.
Публичные состояния монитора и безопасное поведение при отключённом Telegram описаны в `docs/public-monitor-mvp.md`.

## Docker как дополнительный вариант

Docker-файлы сохранены для других окружений, но не являются основным способом развёртывания на VPS:

```bash
cp .env.example .env
# обязательно замените MANUAL_REFRESH_TOKEN
docker compose build backend
docker compose run --rm backend python -m alembic -c alembic.ini upgrade head
docker compose up --build
```

Migration выполняется отдельной явной командой до запуска backend; FastAPI startup её не применяет.

Команда выше рассчитана на новую пустую Docker volume или уже versioned database. Для существующей unversioned legacy volume сначала остановите backend, создайте и проверьте backup, затем выполните в одноразовом container `python -m app.schema verify-legacy`, `python -m alembic -c alembic.ini stamp 0001_legacy_baseline` и только после успешной проверки — `upgrade head`.
