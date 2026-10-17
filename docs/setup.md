# Окружение bank-lab

Учебное банковское приложение: Flutter, Django REST Framework, PostgreSQL.
Все деньги и карты в приложении будут тестовыми.

## Локальная разработка на macOS Apple Silicon

- Git и Homebrew.
- Flutter SDK (включает Dart).
- Android Studio, Android SDK и ARM64 Android Emulator.
- Docker Desktop для Django и PostgreSQL.
- Python 3.12 для локальных команд бэкенда.
- Charles для практики перехвата запросов.

Установка Flutter и Android Studio:

```sh
brew install --cask flutter android-studio
```

В Android Studio необходимо установить Android SDK через Setup Wizard / SDK
Manager и прочитать лицензии перед их принятием. Затем через Device Manager
создать Android-эмулятор с образом ARM64.

Проверка:

```sh
flutter doctor -v
flutter emulators
flutter devices
docker info
docker compose version
```

Официальная инструкция: https://docs.flutter.dev/platform-integration/android/setup

## Репозиторий

https://github.com/FFeerrruummiitt/bank-lab

Репозиторий публичный. Локальные секреты хранятся в `.env`, который исключён
из Git; примеры настроек можно публиковать в `.env.example`.

## Первая версия

Регистрация и вход; экран «Мой банк»; не более двух счетов с одной виртуальной
картой на счёт; один активный депозит; переводы по номеру карты внутри стенда;
история операций и тестовое пополнение. Валюта — KZT.

Бэкенд и база запускаются в Docker, мобильное приложение — в эмуляторе или
на телефоне. Grafana, Loki и Alloy включены в Docker Compose; см. [monitoring.md](monitoring.md).
