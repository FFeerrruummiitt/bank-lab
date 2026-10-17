import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class ApiError implements Exception {
  final String message;
  final int? status;
  ApiError(this.message, [this.status]);
  @override
  String toString() => message;
}

class BankApi {
  static const baseUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.0.2.2:8000/api',
  );
  String? token;
  final http.Client client;
  BankApi({http.Client? client}) : client = client ?? http.Client();

  Future<dynamic> request(String path, {Map<String, dynamic>? data}) async {
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Token $token',
    };
    try {
      final uri = Uri.parse('$baseUrl/$path');
      final response =
          await (data == null
                  ? client.get(uri, headers: headers)
                  : client.post(uri, headers: headers, body: jsonEncode(data)))
              .timeout(const Duration(seconds: 20));
      dynamic body;
      try {
        body = jsonDecode(utf8.decode(response.bodyBytes));
      } on FormatException {
        throw ApiError('Неожиданный ответ сервера (${response.statusCode}).');
      }
      if (response.statusCode >= 400) {
        throw ApiError(_message(body), response.statusCode);
      }
      return body;
    } on TimeoutException {
      throw ApiError(
        'Сервер не ответил вовремя. Операция могла выполниться: обновите баланс и историю. Повтор перевода в этом окне защищён от двойного списания.',
      );
    } on SocketException {
      throw ApiError(
        'Нет соединения с банком. Проверьте сеть и запуск Docker.',
      );
    } on http.ClientException {
      throw ApiError(
        'Связь прервалась. Проверьте баланс и историю перед повтором операции.',
      );
    }
  }

  String _message(dynamic value) {
    if (value is Map) {
      return value.entries
          .map(
            (e) => e.key == 'detail'
                ? _message(e.value)
                : '${e.key}: ${_message(e.value)}',
          )
          .join('\n');
    }
    if (value is List) return value.map(_message).join('\n');
    return value.toString();
  }
}
