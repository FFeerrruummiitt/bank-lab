# Bank Lab mobile

Flutter-приложение учебного банка. Общая инструкция запуска находится в
[README проекта](../README.md), демо-данные и QA-сценарии — в
[docs/testing.md](../docs/testing.md).

Основной интерфейс: `lib/main.dart`. HTTP-клиент: `lib/api.dart`.

```sh
flutter pub get
flutter run -d emulator-5554
```

Django API должен быть запущен через Docker Compose из корня проекта.
