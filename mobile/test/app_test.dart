import 'dart:async';
import 'dart:convert';

import 'package:bank_lab/api.dart';
import 'package:bank_lab/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('Empty login is validated before requesting API', (tester) async {
    await tester.pumpWidget(const BankLabApp());
    await tester.tap(find.text('Войти в банк'));
    await tester.pump();
    expect(find.text('Введите корректный email'), findsOneWidget);
    expect(find.text('Введите пароль'), findsOneWidget);
  });

  testWidgets('Registration passes entered credentials', (tester) async {
    List<dynamic>? submitted;
    await tester.pumpWidget(
      MaterialApp(
        home: AuthScreen(
          busy: false,
          error: null,
          onSubmit: (register, email, password, name) async {
            submitted = [register, email, password, name];
          },
        ),
      ),
    );
    await tester.tap(find.text('Регистрация'));
    await tester.pumpAndSettle();
    final fields = find.byType(TextFormField);
    await tester.enterText(fields.at(0), 'Алия');
    await tester.enterText(fields.at(1), 'aliya@example.com');
    await tester.enterText(fields.at(2), 'Test-password-478!');
    await tester.ensureVisible(find.text('Создать аккаунт'));
    await tester.tap(find.text('Создать аккаунт'));
    await tester.pump();
    expect(submitted, [
      true,
      'aliya@example.com',
      'Test-password-478!',
      'Алия',
    ]);
  });

  testWidgets('Transfer keeps same idempotency key after lost response', (
    tester,
  ) async {
    final requests = <Map<String, dynamic>>[];
    final api = BankApi(
      client: MockClient((request) async {
        requests.add(jsonDecode(request.body));
        if (requests.length == 1) throw TimeoutException('Lost response');
        return http.Response('{"reference":"ok"}', 201);
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => showDialog<void>(
                context: context,
                builder: (_) => OperationDialog(
                  api: api,
                  accounts: const [
                    {
                      'id': 1,
                      'card_number': '9900000000000001',
                      'balance': '1000.00',
                    },
                  ],
                  path: 'transfers/',
                  transfer: true,
                ),
              ),
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextFormField).at(0),
      '9900000000000002',
    );
    await tester.enterText(find.byType(TextFormField).at(1), '125,50');
    await tester.tap(find.text('Перевести'));
    await tester.pumpAndSettle();
    expect(requests.length, 1);
    await tester.ensureVisible(find.text('Перевести'));
    await tester.tap(find.text('Перевести'));
    await tester.pumpAndSettle();
    expect(requests.length, 2);
    expect(requests[0]['request_id'], requests[1]['request_id']);
    expect(requests[1]['amount'], '125.50');
    api.client.close();
  });
}
