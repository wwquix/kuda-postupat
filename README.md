# Монитор вступительной кампании БГЭУ

Сервис получает текущие сведения о поданных документах БГЭУ, хранит историю изменений в SQLite, рассчитывает оценочный текущий порог и показывает dashboard. При необходимости значимые изменения отправляются в Telegram.

> Это автоматическая оценка на основании текущих заявлений, а не официальный итоговый проходной балл. Она не гарантирует поступление.

Источник данных — UTF-8 XML `https://bseu.by/abiturient/xml/1.xml`. Стартовая HTML-страница использует Windows-1251 и загружает этот XML обычным HTTP-запросом; браузерная автоматизация не требуется. Результаты исследования находятся в `docs/source-analysis.md`.

## Быстрый запуск на Windows

Требуются Windows 11, PowerShell 7, Python 3.12+ и Node.js 22+.

```powershell
Set-Location 'C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor'
.\setup.ps1
.\start-dev.ps1
```

Dashboard: `http://127.0.0.1:5173`

Backend API: `http://127.0.0.1:8000`

OpenAPI: `http://127.0.0.1:8000/docs`

`setup.ps1` создаёт `.venv`, устанавливает Python/Node зависимости и, только если `.env` отсутствует, копирует `.env.example` и генерирует случайный `MANUAL_REFRESH_TOKEN`. Значение token не печатается. Существующий `.env` никогда не перезаписывается.

Локально допускается Python новее 3.12 с предупреждением. Production unit использует системный `python3` Ubuntu 24.04.

## Первый запуск

```powershell
Set-Location 'C:\Users\Yura\Documents\Codex\2026-07-12\files-mentioned-by-the-user-production\outputs\bseu-admission-monitor'
.\setup.ps1
.\start-dev.ps1
```

Первый запуск backend автоматически создаёт таблицы SQLite и выполняет live refresh. Если БГЭУ временно недоступен, frontend показывает понятную ошибку и не подставляет фиктивные данные.

## Последующие запуски

```powershell
.\start-dev.ps1
```

PID хранятся в `.runtime`. Повторный запуск проверяет принадлежность PID этому проекту и не создаёт вторые backend, frontend или scheduler.

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

Последовательно выполняются обычные pytest-тесты, отдельный live test, Ruff, ESLint, TypeScript и Vite production build. Первая ошибка завершает скрипт с ненулевым кодом.

Отдельные команды:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m pytest -m live -o addopts=
..\.venv\Scripts\python.exe -m ruff check .

Set-Location ..\frontend
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

Перед копированием создаётся timestamped rollback-копия в `/opt/bseu-admission-monitor-rollbacks`. Environment и SQLite находятся вне каталога кода и не перезаписываются.

## Rollback

Последняя копия:

```bash
sudo /opt/bseu-admission-monitor/deploy/rollback-server.sh
```

Конкретная копия:

```bash
sudo /opt/bseu-admission-monitor/deploy/rollback-server.sh /opt/bseu-admission-monitor-rollbacks/<timestamp>
```

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

- `GET /api/health`
- `GET /api/config` — только публичная конфигурация, без secret values
- `GET /api/status`
- `GET /api/specialties`
- `GET /api/specialties/{id}/latest`
- `GET /api/specialties/{id}/history`
- `GET /api/specialties/{id}/score-distribution`
- `POST /api/refresh` — `X-Refresh-Token` или `Authorization: Bearer ...`

## Docker как дополнительный вариант

Docker-файлы сохранены для других окружений, но не являются основным способом развёртывания на VPS:

```bash
cp .env.example .env
# обязательно замените MANUAL_REFRESH_TOKEN
docker compose up --build
```
