import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:uuid/uuid.dart';

import 'api.dart';

const ink = Color(0xFF143C32);
const lime = Color(0xFFD7F275);
const canvas = Color(0xFFF3F5EF);

void main() => runApp(const BankLabApp());

String money(dynamic value) {
  final parts = (double.tryParse('$value') ?? 0).toStringAsFixed(2).split('.');
  final whole = parts[0].replaceAllMapped(
    RegExp(r'(\d)(?=(\d{3})+(?!\d))'),
    (m) => '${m[1]} ',
  );
  return '$whole,${parts[1]} ₸';
}

String cardLabel(dynamic value) =>
    '$value'.replaceAllMapped(RegExp(r'.{4}'), (m) => '${m[0]} ').trim();

class BankLabApp extends StatelessWidget {
  const BankLabApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Bank Lab',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: canvas,
      colorScheme: ColorScheme.fromSeed(
        seedColor: ink,
        primary: ink,
        secondary: lime,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: canvas,
        foregroundColor: ink,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
    ),
    home: const BankShell(),
  );
}

class BankShell extends StatefulWidget {
  const BankShell({super.key});
  @override
  State<BankShell> createState() => _BankShellState();
}

class _BankShellState extends State<BankShell> {
  final api = BankApi();
  Map<String, dynamic>? bank;
  List<dynamic> history = [];
  dynamic cursor;
  int page = 0;
  bool busy = false;
  String? error;
  List<dynamic> get accounts => bank?['accounts'] ?? [];

  Future<void> load() async {
    final data = await Future.wait([
      api.request('bank/'),
      api.request('history/'),
    ]);
    if (mounted) {
      setState(() {
        bank = Map<String, dynamic>.from(data[0]);
        history = data[1]['results'];
        cursor = data[1]['next'];
      });
    }
  }

  Future<void> perform(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) {
        setState(() {
          error = e is ApiError
              ? e.message
              : 'Не удалось выполнить действие. Повторите позже.';
          if (e is ApiError && e.status == 401 && bank != null) {
            api.token = null;
            bank = null;
            history = [];
            error = 'Сессия завершена. Войдите снова.';
          }
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> authenticate(
    bool register,
    String email,
    String password,
    String name,
  ) => perform(() async {
    final result = await api.request(
      'auth/${register ? 'register' : 'login'}/',
      data: {
        'email': email.trim(),
        'password': password,
        if (register) 'name': name.trim(),
      },
    );
    api.token = result['token'];
    await load();
  });

  Future<void> create(String path) => perform(() async {
    await api.request(path, data: {});
    await load();
  });

  Future<void> operation(
    String path, {
    bool transfer = false,
    bool close = false,
  }) async {
    if (accounts.isEmpty) {
      setState(() => error = 'Сначала откройте счёт в разделе «Мой банк».');
      return;
    }
    final success = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => OperationDialog(
        api: api,
        accounts: accounts,
        path: path,
        transfer: transfer,
        close: close,
      ),
    );
    if (success == true && mounted) {
      await perform(load);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Операция выполнена')));
      }
    }
  }

  @override
  void dispose() {
    api.client.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (bank == null) {
      return AuthScreen(busy: busy, error: error, onSubmit: authenticate);
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'bank lab',
          style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: -1),
        ),
        actions: [
          IconButton(
            tooltip: 'Обновить',
            onPressed: busy ? null : () => perform(load),
            icon: const Icon(Icons.refresh_rounded),
          ),
          IconButton(
            tooltip: 'Выйти',
            onPressed: busy
                ? null
                : () => perform(() async {
                    await api.request('auth/logout/', data: {});
                    if (mounted) {
                      setState(() {
                        api.token = null;
                        bank = null;
                        history = [];
                        page = 0;
                      });
                    }
                  }),
            icon: const Icon(Icons.logout_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          if (busy) const LinearProgressIndicator(minHeight: 2),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: errorBox(error!),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => perform(load),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
                children: [
                  Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 600),
                      child: page == 0
                          ? dashboard()
                          : page == 1
                          ? transferPage()
                          : historyPage(),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: page,
        onDestinationSelected: busy
            ? null
            : (value) => setState(() {
                page = value;
                error = null;
              }),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: 'Мой банк',
          ),
          NavigationDestination(
            icon: Icon(Icons.swap_horiz_rounded),
            label: 'Переводы',
          ),
          NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            label: 'История',
          ),
        ],
      ),
    );
  }

  Widget dashboard() {
    final deposit = bank!['deposit'];
    final total =
        accounts.fold<double>(0, (sum, a) => sum + double.parse(a['balance'])) +
        (deposit == null ? 0 : double.parse(deposit['balance']));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Привет, ${bank!['name']} 👋',
          style: const TextStyle(fontSize: 17, color: ink),
        ),
        const SizedBox(height: 24),
        const Text('Ваши деньги', style: TextStyle(color: Colors.black54)),
        const SizedBox(height: 4),
        Text(
          money(total),
          style: const TextStyle(
            fontSize: 36,
            fontWeight: FontWeight.w800,
            letterSpacing: -1.5,
            color: ink,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Счета и депозит · KZT',
          style: TextStyle(color: Colors.black54),
        ),
        const SizedBox(height: 24),
        Row(
          children: [
            Expanded(
              child: actionTile(
                Icons.add_rounded,
                'Пополнить',
                bank!['test_mode'] == true && !busy
                    ? () => operation('topup/')
                    : null,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: actionTile(
                Icons.north_east_rounded,
                'Перевести',
                busy ? null : () => operation('transfers/', transfer: true),
              ),
            ),
          ],
        ),
        const SizedBox(height: 28),
        section('Счета и карты', '${accounts.length} / 2'),
        if (accounts.isEmpty)
          empty(
            'Первый шаг — ваша карта',
            'Откройте счёт для переводов и тестовых пополнений.',
            Icons.credit_card_rounded,
          ),
        for (final a in accounts)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: accountCard(a),
          ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: busy || accounts.length >= 2
              ? null
              : () => create('accounts/'),
          icon: const Icon(Icons.add),
          label: Text(
            accounts.length >= 2
                ? 'Открыто 2 из 2 счетов'
                : 'Открыть счёт и карту',
          ),
        ),
        const SizedBox(height: 28),
        section('Депозит', deposit == null ? '0 / 1' : '1 / 1'),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(24),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.savings_outlined, color: ink),
                  const SizedBox(width: 10),
                  Text(
                    deposit == null ? 'Копите на свои цели' : 'Мой депозит',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                deposit == null
                    ? 'Без процентов и комиссий.'
                    : money(deposit['balance']),
                style: TextStyle(fontSize: deposit == null ? 14 : 26),
              ),
              const SizedBox(height: 14),
              if (deposit == null)
                FilledButton(
                  onPressed: busy ? null : () => create('deposits/'),
                  child: const Text('Открыть депозит'),
                )
              else
                Wrap(
                  spacing: 8,
                  children: [
                    FilledButton(
                      onPressed: busy
                          ? null
                          : () => operation('deposits/topup/'),
                      child: const Text('Пополнить'),
                    ),
                    TextButton(
                      onPressed: busy
                          ? null
                          : () => operation('deposits/close/', close: true),
                      child: const Text('Закрыть'),
                    ),
                  ],
                ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        const Text(
          'Учебный банк · Все деньги вымышленные',
          style: TextStyle(fontSize: 12, color: Colors.black54),
        ),
      ],
    );
  }

  Widget accountCard(dynamic a) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(24),
      gradient: LinearGradient(
        colors: a['slot'] == 1
            ? [ink, const Color(0xFF286451)]
            : [const Color(0xFF283D61), const Color(0xFF4A6488)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'LAB / Счёт ${a['slot']}',
              style: const TextStyle(color: Colors.white70),
            ),
            const Icon(Icons.contactless_outlined, color: Colors.white70),
          ],
        ),
        const SizedBox(height: 22),
        Text(
          money(a['balance']),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 28,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 18),
        Row(
          children: [
            Expanded(
              child: Text(
                cardLabel(a['card_number']),
                style: const TextStyle(
                  color: Colors.white,
                  letterSpacing: 1.4,
                  fontSize: 15,
                ),
              ),
            ),
            IconButton(
              tooltip: 'Скопировать номер карты',
              icon: const Icon(
                Icons.copy_rounded,
                color: Colors.white70,
                size: 18,
              ),
              onPressed: () {
                Clipboard.setData(ClipboardData(text: a['card_number']));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Номер тестовой карты скопирован'),
                  ),
                );
              },
            ),
          ],
        ),
        const Text(
          'Виртуальная тестовая карта',
          style: TextStyle(color: Colors.white54, fontSize: 11),
        ),
      ],
    ),
  );

  Widget transferPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading('Переводы'),
      const SizedBox(height: 10),
      const Text('На карты Bank Lab. Без комиссии.'),
      const SizedBox(height: 24),
      empty(
        'По номеру карты',
        'Нужен полный 16-значный номер карты получателя. Можно переводить и между своими счетами.',
        Icons.swap_horiz_rounded,
      ),
      const SizedBox(height: 20),
      SizedBox(
        width: double.infinity,
        child: FilledButton.icon(
          onPressed: busy
              ? null
              : () => operation('transfers/', transfer: true),
          icon: const Icon(Icons.north_east),
          label: const Text('Новый перевод'),
        ),
      ),
      const SizedBox(height: 20),
      const Text(
        'Для перевода другому пользователю зарегистрируйте второй аккаунт и откройте в нём карту. Скопируйте её номер, затем вернитесь в свой аккаунт.',
        style: TextStyle(color: Colors.black54, height: 1.6),
      ),
    ],
  );

  Widget historyPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading('История'),
      const SizedBox(height: 8),
      const Text('Все движения по вашим счетам'),
      const SizedBox(height: 24),
      if (history.isEmpty)
        empty(
          'Пока без операций',
          'Пополните счёт или отправьте первый перевод.',
          Icons.receipt_long_outlined,
        ),
      for (final row in history)
        Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                backgroundColor: canvas,
                foregroundColor: ink,
                child: Icon(
                  double.parse(row['amount']) < 0
                      ? Icons.north_east
                      : Icons.south_west,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      row['title'],
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      _date(row['created_at']),
                      style: const TextStyle(
                        color: Colors.black54,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${double.parse(row['amount']) > 0 ? '+' : ''}${money(row['amount'])}',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        color: double.parse(row['amount']) > 0
                            ? const Color(0xFF287B49)
                            : ink,
                      ),
                    ),
                    Text(
                      'Остаток: ${money(row['balance_after'])}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Colors.black54,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      if (cursor != null)
        TextButton(
          onPressed: busy
              ? null
              : () => perform(() async {
                  final result = await api.request('history/?before=$cursor');
                  if (mounted) {
                    setState(() {
                      history.addAll(result['results']);
                      cursor = result['next'];
                    });
                  }
                }),
          child: const Text('Загрузить ещё'),
        ),
    ],
  );

  String _date(String value) {
    final date = DateTime.parse(value).toLocal();
    String two(int n) => '$n'.padLeft(2, '0');
    return '${two(date.day)}.${two(date.month)}.${date.year} · ${two(date.hour)}:${two(date.minute)}';
  }
}

Widget heading(String title) => Text(
  title,
  style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: ink),
);
Widget errorBox(String text) => Container(
  width: double.infinity,
  padding: const EdgeInsets.all(14),
  margin: const EdgeInsets.only(bottom: 12),
  decoration: BoxDecoration(
    color: const Color(0xFFFFE9E4),
    borderRadius: BorderRadius.circular(16),
  ),
  child: Text(text, style: const TextStyle(color: Color(0xFF9C3322))),
);
Widget section(String title, String note) => Row(
  mainAxisAlignment: MainAxisAlignment.spaceBetween,
  children: [
    Text(
      title,
      style: const TextStyle(
        fontSize: 21,
        fontWeight: FontWeight.w700,
        color: ink,
      ),
    ),
    Text(note, style: const TextStyle(color: Colors.black45)),
  ],
);
Widget empty(String title, String text, IconData icon) => Container(
  width: double.infinity,
  padding: const EdgeInsets.all(24),
  margin: const EdgeInsets.only(top: 12),
  decoration: BoxDecoration(
    color: Colors.white,
    borderRadius: BorderRadius.circular(24),
  ),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(icon, size: 32, color: ink),
      const SizedBox(height: 16),
      Text(
        title,
        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 8),
      Text(text, style: const TextStyle(color: Colors.black54, height: 1.5)),
    ],
  ),
);
Widget actionTile(IconData icon, String label, VoidCallback? onTap) =>
    FilledButton.tonal(
      style: FilledButton.styleFrom(
        backgroundColor: lime,
        foregroundColor: ink,
        padding: const EdgeInsets.symmetric(vertical: 18),
      ),
      onPressed: onTap,
      child: Column(
        children: [
          Icon(icon, size: 28),
          const SizedBox(height: 8),
          Text(label),
        ],
      ),
    );

class AuthScreen extends StatefulWidget {
  final bool busy;
  final String? error;
  final Future<void> Function(bool, String, String, String) onSubmit;
  const AuthScreen({
    super.key,
    required this.busy,
    required this.error,
    required this.onSubmit,
  });
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final form = GlobalKey<FormState>();
  final email = TextEditingController(),
      password = TextEditingController(),
      name = TextEditingController();
  bool register = false, hidden = true;
  @override
  void dispose() {
    email.dispose();
    password.dispose();
    name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Form(
              key: form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: ink,
                      borderRadius: BorderRadius.circular(22),
                    ),
                    child: const Icon(
                      Icons.account_balance_rounded,
                      color: lime,
                      size: 32,
                    ),
                  ),
                  const SizedBox(height: 28),
                  const Text(
                    'bank lab',
                    style: TextStyle(
                      fontSize: 42,
                      letterSpacing: -2,
                      fontWeight: FontWeight.w800,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    register
                        ? 'Ваш первый шаг в учебный банк'
                        : 'Ваш банк. Ваша практика.',
                    style: const TextStyle(fontSize: 18, color: Colors.black54),
                  ),
                  const SizedBox(height: 32),
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: false, label: Text('Вход')),
                      ButtonSegment(value: true, label: Text('Регистрация')),
                    ],
                    selected: {register},
                    onSelectionChanged: widget.busy
                        ? null
                        : (value) => setState(() => register = value.first),
                  ),
                  const SizedBox(height: 24),
                  if (widget.error != null) errorBox(widget.error!),
                  if (register) ...[
                    TextFormField(
                      controller: name,
                      enabled: !widget.busy,
                      maxLength: 100,
                      decoration: const InputDecoration(
                        labelText: 'Как вас зовут?',
                      ),
                      validator: (v) =>
                          v == null || v.trim().isEmpty ? 'Введите имя' : null,
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextFormField(
                    controller: email,
                    enabled: !widget.busy,
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      prefixIcon: Icon(Icons.alternate_email),
                    ),
                    validator: (v) =>
                        v == null ||
                            !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                                .hasMatch(v.trim())
                        ? 'Введите корректный email'
                        : null,
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: password,
                    enabled: !widget.busy,
                    obscureText: hidden,
                    autocorrect: false,
                    decoration: InputDecoration(
                      labelText: 'Пароль',
                      prefixIcon: const Icon(Icons.lock_outline),
                      suffixIcon: IconButton(
                        tooltip: hidden ? 'Показать пароль' : 'Скрыть пароль',
                        icon: Icon(
                          hidden
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                        onPressed: () => setState(() => hidden = !hidden),
                      ),
                    ),
                    validator: (v) => v == null || v.isEmpty
                        ? 'Введите пароль'
                        : register && v.length < 8
                        ? 'Минимум 8 символов'
                        : null,
                  ),
                  if (register)
                    const Padding(
                      padding: EdgeInsets.only(top: 10),
                      child: Text(
                        'Минимум 8 символов. Не используйте простой пароль или только цифры.',
                        style: TextStyle(fontSize: 12, color: Colors.black54),
                      ),
                    ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: widget.busy
                          ? null
                          : () {
                              if (form.currentState!.validate()) {
                                widget.onSubmit(
                                  register,
                                  email.text,
                                  password.text,
                                  name.text,
                                );
                              }
                            },
                      child: widget.busy
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(register ? 'Создать аккаунт' : 'Войти в банк'),
                    ),
                  ),
                  const SizedBox(height: 28),
                  const Text(
                    'Учебное приложение для тестирования.\nВсе карты и средства вымышленные.',
                    style: TextStyle(
                      color: Colors.black45,
                      fontSize: 12,
                      height: 1.6,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

class OperationDialog extends StatefulWidget {
  final BankApi api;
  final List<dynamic> accounts;
  final String path;
  final bool transfer, close;
  const OperationDialog({
    super.key,
    required this.api,
    required this.accounts,
    required this.path,
    this.transfer = false,
    this.close = false,
  });
  @override
  State<OperationDialog> createState() => _OperationDialogState();
}

class _OperationDialogState extends State<OperationDialog> {
  final form = GlobalKey<FormState>();
  final amount = TextEditingController(), card = TextEditingController();
  late int accountId = widget.accounts.first['id'];
  bool busy = false;
  String? error, fingerprint, requestId;
  @override
  void dispose() {
    amount.dispose();
    card.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    final data = <String, dynamic>{'account_id': accountId};
    if (!widget.close) data['amount'] = amount.text.trim().replaceAll(',', '.');
    if (widget.transfer) {
      data['card_number'] = card.text.replaceAll(' ', '');
      final current = '$accountId|${data['card_number']}|${data['amount']}';
      if (fingerprint != current) {
        fingerprint = current;
        requestId = const Uuid().v4();
      }
      data['request_id'] = requestId;
    }
    try {
      await widget.api.request(widget.path, data: data);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is ApiError
              ? e.message
              : 'Не удалось выполнить операцию.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: Text(
        widget.transfer
            ? 'Перевод на карту'
            : widget.close
            ? 'Закрыть депозит?'
            : widget.path == 'topup/'
            ? 'Тестовое пополнение'
            : 'Пополнить депозит',
      ),
      content: SingleChildScrollView(
        child: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (error != null) errorBox(error!),
              if (widget.close)
                const Padding(
                  padding: EdgeInsets.only(bottom: 18),
                  child: Text(
                    'Весь баланс депозита вернётся на выбранный счёт.',
                  ),
                ),
              DropdownButtonFormField<int>(
                initialValue: accountId,
                isExpanded: true,
                decoration: InputDecoration(
                  labelText: widget.close ? 'Вернуть деньги на счёт' : 'Счёт',
                ),
                items: widget.accounts
                    .map(
                      (a) => DropdownMenuItem<int>(
                        value: a['id'],
                        child: Text(
                          '•• ${a['card_number'].toString().substring(12)} · ${money(a['balance'])}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    )
                    .toList(),
                onChanged: busy
                    ? null
                    : (value) => setState(() => accountId = value!),
              ),
              if (widget.transfer) ...[
                const SizedBox(height: 16),
                TextFormField(
                  controller: card,
                  enabled: !busy,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Номер карты получателя',
                  ),
                  validator: (v) =>
                      !RegExp(r'^9900[0-9]{12}$')
                          .hasMatch((v ?? '').replaceAll(' ', ''))
                      ? 'Введите 16 цифр тестовой карты'
                      : null,
                ),
              ],
              if (!widget.close) ...[
                const SizedBox(height: 16),
                TextFormField(
                  controller: amount,
                  enabled: !busy,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Сумма, ₸',
                    helperText: 'От 0,01 до 1 000 000 ₸',
                  ),
                  validator: (v) {
                    final text = (v ?? '').trim().replaceAll(',', '.');
                    final number = double.tryParse(text);
                    return !RegExp(r'^\d{1,7}(\.\d{1,2})?$').hasMatch(text) ||
                            number == null ||
                            number <= 0 ||
                            number > 1000000
                        ? 'Введите сумму от 0,01 до 1 000 000'
                        : null;
                  },
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: busy ? null : () => Navigator.pop(context, false),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: busy ? null : submit,
          child: Text(
            busy
                ? 'Выполняется…'
                : widget.close
                ? 'Закрыть депозит'
                : widget.transfer
                ? 'Перевести'
                : 'Пополнить',
          ),
        ),
      ],
    ),
  );
}
