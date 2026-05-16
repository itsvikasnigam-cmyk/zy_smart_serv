/// Base URL for `billing_api` (subscriptions, invoices). Same JWT as `client_api`.
///
/// `flutter run --dart-define=BILLING_API_BASE_URL=http://127.0.0.1:8086`
class BillingApiConfig {
  BillingApiConfig({String? baseUrl})
      : apiBaseUrl = (baseUrl ?? _fromDefine).replaceAll(RegExp(r'/+$'), '');

  static const _fromDefine = String.fromEnvironment(
    'BILLING_API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8086',
  );

  final String apiBaseUrl;

  Uri rest(String path, [Map<String, String>? query]) {
    final p = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$apiBaseUrl$p').replace(queryParameters: query);
  }
}
