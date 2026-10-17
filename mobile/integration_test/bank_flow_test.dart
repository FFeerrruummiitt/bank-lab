import 'package:bank_lab/api.dart';
import 'package:bank_lab/main.dart' as app;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Register, two cards, top up, transfer, deposit, history', (
    tester,
  ) async {
    final email =
        'android-${DateTime.now().millisecondsSinceEpoch}@banklab.test';
    const password = 'Android-test-478!';
    final api = BankApi();
    addTearDown(() => api.client.close());

    Future<void> settleUntil(Finder target) async {
      for (var i = 0; i < 100; i++) {
        await tester.pump(const Duration(milliseconds: 200));
        if (target.evaluate().isNotEmpty &&
            find.byType(LinearProgressIndicator).evaluate().isEmpty) {
          await tester.pumpAndSettle();
          return;
        }
      }
      expect(target, findsWidgets);
    }

    Future<void> tap(String label) async {
      final target = find.text(label).last;
      await Scrollable.ensureVisible(tester.element(target), alignment: 0.5);
      await tester.pumpAndSettle();
      expect(target.hitTestable(), findsOneWidget);
      await tester.tap(target);
      await tester.pumpAndSettle();
    }

    Future<void> finishOperation() async {
      for (
        var i = 0;
        i < 100 && find.byType(AlertDialog).evaluate().isNotEmpty;
        i++
      ) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(find.byType(AlertDialog), findsNothing);
      await settleUntil(find.text('Счета и карты'));
    }

    app.main();
    await tester.pumpAndSettle();
    await tap('Регистрация');
    await tester.enterText(find.byType(TextFormField).at(0), 'Android QA');
    await tester.enterText(find.byType(TextFormField).at(1), email);
    await tester.enterText(find.byType(TextFormField).at(2), password);
    await tap('Создать аккаунт');
    await settleUntil(find.text('Счета и карты'));

    await tap('Открыть счёт и карту');
    await settleUntil(find.text('1 / 2'));
    await tap('Открыть счёт и карту');
    await settleUntil(find.text('2 / 2'));
    expect(find.text('Открыто 2 из 2 счетов'), findsOneWidget);

    final auth = await api.request(
      'auth/login/',
      data: {'email': email, 'password': password},
    );
    api.token = auth['token'];
    final initial = await api.request('bank/');
    final recipient = initial['accounts'][1]['card_number'];

    await tap('Пополнить');
    await tester.enterText(find.byType(TextFormField).last, '1000');
    await tap('Пополнить');
    await finishOperation();

    await tap('Перевести');
    await tester.enterText(find.byType(TextFormField).at(0), recipient);
    await tester.enterText(find.byType(TextFormField).at(1), '125,50');
    await tap('Перевести');
    await finishOperation();
    var state = await api.request('bank/');
    expect(state['accounts'][0]['balance'], '874.50');
    expect(state['accounts'][1]['balance'], '125.50');

    await tap('Открыть депозит');
    await settleUntil(find.text('Мой депозит'));
    await tap('Пополнить');
    await tester.enterText(find.byType(TextFormField).last, '50');
    await tap('Пополнить');
    await finishOperation();
    state = await api.request('bank/');
    expect(state['deposit']['balance'], '50.00');
    expect(state['accounts'][0]['balance'], '824.50');

    await tap('История');
    expect(find.text('Пополнение депозита'), findsOneWidget);
    expect(find.text('Тестовое пополнение'), findsOneWidget);
    await tester.tap(find.byTooltip('Выйти'));
    await tester.pumpAndSettle();
    await settleUntil(find.text('Войти в банк'));
  });
}
