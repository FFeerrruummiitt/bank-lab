# Grafana, Loki и Alloy

## Вход

Откройте http://localhost:3001/d/bank-lab-api.

- Логин: `admin`.
- Пароль: значение `GRAFANA_ADMIN_PASSWORD` в локальном `.env` в корне проекта.
- Дашборд: **Bank Lab · API и логи**, папка **Bank Lab**.

Порт 3000 на этом компьютере занят другим приложением. Для изменения порта
добавьте `GRAFANA_PORT=3002` в `.env` и запустите `docker compose up -d grafana`.

```sh
make up
make monitoring-check
```

`init_env.py` добавляет недостающие секреты и сохраняет существующие пароли
базы и Grafana. Изменение пароля в `.env` после первого запуска Grafana
не меняет пароль существующего пользователя в её базе. Меняйте пароль через
профиль Grafana и синхронизируйте `.env`, чтобы работал `monitoring-check`.

## Что показывает дашборд

1. Количество HTTP-запросов за выбранный период.
2. Ошибки клиента — ответы 4xx, включая неверный вход, нехватку средств и лимиты.
3. Ошибки сервера — ответы 5xx.
4. p95 времени ответа: 95% запросов выполнились не дольше этого времени.
5. Графики запросов по статусам, времени ответа и ошибок по адресу API.
6. Журнал запросов с поиском по Request ID.

По умолчанию выбран последний час; обновление каждые 5 секунд. Новому запросу
обычно нужно несколько секунд для появления в Loki. До первых запросов
графики могут быть пустыми.

Дашборд собирается из логов; Prometheus для этих графиков не требуется.
Исторические `docker compose logs` до подключения файлового журнала не импортируются.

## Найти конкретную ошибку

1. Выполните запрос через приложение, Swagger или прокси.
2. Скопируйте заголовок ответа `X-Request-ID` из Swagger/Charles.
3. Вставьте его в поле **Request ID** вверху дашборда и нажмите Enter.
4. Откройте панель логов внизу и разверните запись.

Поле Request ID фильтрует журнал; сводные графики остаются за весь выбранный период.

В **Explore**, выбрав **Bank Lab Loki**, можно выполнять LogQL:

```logql
{service="bank-api", environment="local"}
```

Все ошибочные HTTP-ответы:

```logql
{service="bank-api"} | json | status >= 400 | __error__=""
```

Только переводы:

```logql
{service="bank-api"} | json | path = "/api/transfers/"
```

Запрос дольше 500 миллисекунд:

```logql
{service="bank-api"} | json | duration_ms > 500 | __error__=""
```

## Учебный сценарий

Попробуйте третий счёт через Swagger или перевод больше баланса.
В Grafana появится HTTP 400, адрес API и время ответа. Посмотрите
`request_id`, затем найдите эту же запись в логах контейнера:

```sh
docker compose logs backend
```

В первой версии в Loki отправляется структурированный журнал HTTP-запросов.
Traceback необработанного исключения и служебные логи Gunicorn доступны
через `docker compose logs backend`.

## Как устроена доставка

```text
Django / Gunicorn (2 процесса)
  → JSON-файл в отдельном Docker volume bank-logs
  → Alloy (читает volume только для чтения)
  → Loki (хранит и обрабатывает запросы)
  → Grafana (показывает дашборд и Explore)
```

Два процесса Django используют ConcurrentRotatingFileHandler с межпроцессной
блокировкой. Файлы ротируются примерно по 5 МБ; сохраняются три резервных
файла. Alloy отслеживает основной файл и хранит позицию чтения в своём volume.
Ему не нужен доступ к Docker socket или контейнерам других проектов.

В Loki настроено хранение 7 дней с асинхронным удалением компактором.
Это локальная файловая установка в одном экземпляре. Состояние Loki, Alloy,
Grafana и журнал Django находятся в отдельных Docker volumes и сохраняются
после обычного перезапуска. `docker compose down -v` удалит volumes, включая
банковскую базу — для остановки используйте `make stop`.

Лог содержит только timestamp, level, service, request_id, method, path,
status, duration_ms, а при активной трассе — trace_id и span_id. Пароли, токены, тела запросов, номера карт и query string
не записываются. В Loki индексируются только ограниченные метки, включая
service, environment и level; request_id остаётся полем JSON.

Grafana опубликована только на 127.0.0.1. Loki, Tempo и Alloy доступны внутри
Docker-сети проекта. Данные в Grafana открываются после входа.

## Проверка и диагностика

```sh
make monitoring-check
docker compose ps
docker compose logs --tail=50 alloy loki grafana
```

Проверка создаёт один успешный запрос и один ожидаемый 401 без изменения
банковских данных. Она сверяет X-Request-ID с записью в Loki и выполняет
все запросы графиков. Проверку старой записи после перезапуска можно повторить:

```sh
docker compose restart loki alloy grafana
python3 scripts/check_monitoring.py --request-id UUID_ИЗ_ПРЕДЫДУЩЕЙ_ПРОВЕРКИ
```

Конфигурация находится в `infrastructure/`: `alloy/config.alloy`,
`loki/config.yaml`, `grafana/provisioning/` и `grafana/dashboards/bank-lab.json`.

Документация: [сбор файлов Alloy](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/),
[provisioning Grafana](https://grafana.com/docs/grafana/latest/administration/provisioning/),
[retention Loki](https://grafana.com/docs/loki/latest/operations/storage/retention/).

## Трассы

В записи лога появятся `trace_id`, `span_id` и ссылка **Открыть трассу**.
[Как искать трассу, читать шаги и работать с прокси](tracing.md).
