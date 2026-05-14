/// Base URL for `ops_api` (SOP Center). Same JWT as `client_api` (`Authorization: Bearer`).
///
/// Override: `flutter run --dart-define=OPS_API_BASE_URL=http://127.0.0.1:8087`
class OpsApiConfig {
  OpsApiConfig({String? baseUrl})
      : apiBaseUrl = _normalizeBase(
          baseUrl ??
              const String.fromEnvironment(
                'OPS_API_BASE_URL',
                defaultValue: 'http://127.0.0.1:8087',
              ),
        );

  final String apiBaseUrl;

  static String _normalizeBase(String raw) {
    var s = raw.trim();
    if (s.endsWith('/')) {
      s = s.substring(0, s.length - 1);
    }
    return s;
  }

  Uri rest(String path, [Map<String, String>? query]) {
    final p = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$apiBaseUrl$p').replace(queryParameters: query);
  }
}
