# Трассы запросов: OpenTelemetry, Tempo и Grafana

## Что добавлено

Django автоматически создаёт серверный span на HTTP-запрос. Psycopg создаёт
дочерние spans на SQL-запросы. В коде перевода добавлены `bank.transfer`,
`bank.validate` и `bank.balance_change` — изменение баланса вызывается дважды,
для отправителя и получателя. Span — отдельный шаг со временем начала,
длительностью и результатом. Трасса — дерево связанных шагов.

```text
Flutter / Swagger / Charles
  → Django: HTTP span
      → PostgreSQL: авторизация
      → bank.transfer (включая завершение транзакции)
          → bank.validate
          → PostgreSQL: блокировки и проверка повтора
          → bank.balance_change → UPDATE, INSERT
          → bank.balance_change → UPDATE, INSERT
```

Трассировка сейчас начинается на Django. Собственные spans Flutter и время
передачи по мобильной сети не собираются. Входящий корректный `traceparent`
позволяет продолжить родительскую трассу; без него Django создаёт новую.

## Четыре разных идентификатора

| Поле | Назначение | При повторной отправке перевода |
|---|---|---|
| `X-Request-ID` в ответе / `request_id` в логе | Один HTTP-запрос, UUID создаёт сервер | Новый |
| `X-Trace-ID` в ответе / `trace_id` в логе | Вся цепочка обработки, 32 hex-символа | Обычно новый; может быть общий при переданном контексте |
| `span_id` | Один шаг внутри трассы, 16 hex-символов; в HTTP-логе это серверный span | Новый |
| `request_id` в JSON **тела перевода** | Ключ идемпотентности банковской операции | Тот же для повтора той же операции |

Последнее поле не является ни Trace ID, ни HTTP Request ID. Оно уже было
в приложении и защищает от повторного списания при повторе запроса.
Не меняйте его при retry той же операции.

## Как это доставляется

```text
Django → JSON-файл → Alloy → Loki ──┐
                                   ├→ Grafana
OpenTelemetry SDK → Alloy → Tempo ──┘
```

SDK отправляет spans фоном пакетами, обычно за несколько секунд.
Alloy удаляет SQL-текст, URL с query string и текст исключений из трасс,
затем передаёт spans в Tempo. Названия SQL-операций и длительности остаются.
Пароли, токены, тела запросов и полные номера карт не добавляются в spans.
Логи содержат метаданные запроса и три идентификатора корреляции.

Трассировка включается в каждом Gunicorn worker после запуска процесса;
миграции и `manage.py test` не отправляют трассы. Health-check исключён.
По умолчанию SDK собирает все новые локальные трассы; входящий флаг sampling
в `traceparent` учитывается. При `...-00` контекст может быть в ответе и логе,
но самой трассы в Tempo не будет.

Tempo работает одним процессом без Kafka, хранит данные в Docker volume
`tempo-data`. Loki, Tempo и приёмник Alloy доступны только внутри Docker-сети.
При недоступном Alloy запрос к банку продолжает работать; очередь SDK ограничена,
поэтому длительная недоступность может привести к потере трасс. Это учебный стенд.

## Найти свой перевод

1. Откройте [Grafana](http://localhost:3001/d/bank-lab-api), войдите как `admin`.
   Пароль — `GRAFANA_ADMIN_PASSWORD` в локальном `.env`.
2. Сделайте перевод в приложении или Swagger.
3. На дашборде раскройте запись `/api/transfers/` в панели логов.
   В Explore с источником **Bank Lab Loki** также можно выполнить:

```logql
{service="bank-api"} | json | path = "/api/transfers/"
```

4. В раскрытой записи нажмите **Открыть трассу** у **TraceID**.
   Если ссылка не показалась в панели дашборда, откройте панель в Explore.
5. В Tempo смотрите дерево и длительности. Родитель включает время дочерних
   шагов: складывать их длительности нельзя. Длинный SQL-span помогает найти
   место задержки, но сам по себе не доказывает её причину.
6. Из трассы можно перейти обратно к логам через **Logs for this span**.
   Запрос использует общий Trace ID.

Можно открыть Explore → **Bank Lab Tempo** → тип запроса **Trace ID**
и вставить значение заголовка ответа `X-Trace-ID`. Для поиска новых трасс:

```traceql
{ resource.service.name = "bank-api" }
```

## Практика с Charles / Proxyman / Swagger

В ответе API смотрите `X-Request-ID` и `X-Trace-ID`. В Grafana найдите запись:

```logql
{service="bank-api"} | json | trace_id = "ВСТАВЬТЕ_TRACE_ID"
```

Для проверки распространения контекста добавьте **в запрос** заголовок:

```http
traceparent: 00-11111111111111111111111111111111-2222222222222222-01
```

На этот запрос сервер вернёт `X-Trace-ID: 11111111111111111111111111111111`.
В Tempo серверный span получит родителя `2222222222222222`; сам родитель
не появится, поскольку прокси не отправляет его span в Tempo.
Для следующего независимого запроса используйте другой Trace ID.
Некорректный `traceparent` игнорируется и создаётся новый контекст.
Один `X-Trace-ID` в запросе контекст не передаёт — нужен `traceparent`.

## Запуск и проверка

```sh
make up
make test
make monitoring-check
make tracing-check
```

`tracing-check` создаёт отдельного учебного пользователя, два счёта, пополнение
на 1 тенге и перевод 0.01 тенге. Он проверяет spans PostgreSQL, входящий контекст,
связь лога с серверным span, отсутствие секретов в трассе, повтор перевода
без нового списания и обработку некорректного контекста. Пользователь и его
история остаются в учебной базе; каждый запуск создаёт нового пользователя.
Alice/Bob не изменяются.

После редактирования конфигураций, смонтированных файлами:

```sh
docker compose restart alloy grafana tempo
```

Код: `backend/bank/tracing.py`, `backend/bank/logging.py`,
`infrastructure/alloy/config.alloy`, `infrastructure/tempo/config.yaml`,
`infrastructure/grafana/provisioning/datasources/loki.yaml`.

Документация: [OpenTelemetry Django](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/django/django.html),
[Tempo single binary](https://github.com/grafana/tempo/tree/v3.1.0/example/docker-compose/single-binary),
[ссылки из Loki](https://grafana.com/docs/grafana/latest/datasources/loki/configure/).
