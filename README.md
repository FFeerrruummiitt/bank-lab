# Bank Lab

Учебный банк для практики мобильного и API-тестирования: Flutter + Django REST Framework + PostgreSQL.
Все карты и деньги вымышленные. Стенд запускается локально.

## Возможности

- Регистрация, вход по email и паролю, выход с отзывом токена.
- «Мой банк»: общий баланс, максимум два счёта с виртуальной картой на каждый.
- Один активный депозит: открытие, пополнение со своего счёта, закрытие с возвратом средств.
- Переводы по номеру карты между пользователями и своими счетами.
- История операций с пагинацией, тестовое пополнение, сообщения об ошибках сети.
- Swagger/OpenAPI, JSON-логи с идентификаторами запросов.
- Grafana + Loki + Alloy: дашборд запросов, ошибок, задержек и поиск по Request ID.

Денежные расчёты выполняет сервер через Decimal. PostgreSQL-транзакции и блокировки
защищают баланс; повтор перевода с тем же request_id не списывает деньги дважды.

## Запуск сервера

Нужны Docker Desktop, Docker Compose и Python 3 для генерации локального .env.

```sh
make up
```

Или без Make:

```sh
python3 scripts/init_env.py
docker compose up -d --build --wait
docker compose exec -T backend python manage.py seed_demo
```

Секреты генерируются локально и не включаются в Git. Данные PostgreSQL сохраняются
в Docker volume. Сервер слушает только 127.0.0.1:8000; порт базы не публикуется.
Базовый Python-образ загружается из публичного зеркала AWS ECR.

- API: http://localhost:8000/api/health/
- Swagger: http://localhost:8000/api/docs/
- OpenAPI: http://localhost:8000/api/schema/
- Grafana: http://localhost:3001/d/bank-lab-api

Вход в Grafana: `admin`, пароль — `GRAFANA_ADMIN_PASSWORD` в локальном `.env`.
Порт 3000 занят другим приложением. Подробности: [docs/monitoring.md](docs/monitoring.md).

## Запуск Android

```sh
cd mobile
flutter pub get
flutter emulators
flutter emulators --launch BankLab_API_36
flutter devices
flutter run -d emulator-5554
```

Имя эмулятора и ID зависят от компьютера. API по умолчанию —
http://10.0.2.2:8000/api (компьютер из Android Emulator). Альтернативный адрес:

```sh
flutter run -d emulator-5554 --dart-define=API_URL=http://10.0.2.2:8000/api
```

Debug APK:

```sh
flutter build apk --debug --target-platform android-arm64
```

Результат: mobile/build/app/outputs/flutter-apk/app-debug.apk.
Токен хранится в памяти; после перезапуска приложения нужно войти заново.
Для входа доступны alice@banklab.test и bob@banklab.test с паролем Lab-demo-478!.
Можно зарегистрировать свой учебный аккаунт.

## Проверки

```sh
make test
make monitoring-check
cd mobile
flutter analyze
flutter test test
flutter drive --driver=test_driver/integration_test.dart --target=integration_test/bank_flow_test.dart -d emulator-5554 --no-dds
```

Серверные тесты выполняются на отдельной PostgreSQL-базе и проверяют ограничения,
точность балансов, доступ к чужим данным и параллельные запросы.

## Управление

```sh
make logs
make stop
```

Изменения backend требуют `docker compose up -d --build backend`.
Повторный seed_demo не сбрасывает пользователей и балансы.

## Структура

- mobile/lib — Flutter-интерфейс и API-клиент.
- backend/bank — модели, API, транзакции, миграции и тесты.
- compose.yaml — Django, PostgreSQL, Grafana, Loki и Alloy.
- infrastructure/ — настройки мониторинга и автоматически создаваемый дашборд.
- docs/testing.md — демо-данные, сценарии QA, Charles и логи.
- docs/setup.md — установка окружения.

Следующие этапы: HTTPS и практика прокси, сохранение сессии
в защищённом хранилище. Счета не закрываются; депозит без процентов; одна валюта KZT.
