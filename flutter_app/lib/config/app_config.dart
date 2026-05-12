/// Base URL for `client_api` (REST). WebSocket uses the same host with `ws`/`wss`.
///
/// Override at build/run time:
/// `flutter run --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085`
class AppConfig {
  AppConfig({String? baseUrl})
      : apiBaseUrl = _normalizeBase(
          baseUrl ??
              const String.fromEnvironment(
                'CLIENT_API_BASE_URL',
                defaultValue: 'http://127.0.0.1:8085',
              ),
        );

  /// Normalized origin without trailing slash.
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

  Uri websocketUri({required String token, String? clientId}) {
    final base = Uri.parse(apiBaseUrl);
    final scheme = base.scheme == 'https' ? 'wss' : 'ws';
    final qp = <String, String>{'token': token};
    if (clientId != null && clientId.isNotEmpty) {
      qp['client_id'] = clientId;
    }
    return base.replace(scheme: scheme, path: '/ws', queryParameters: qp);
  }
}
