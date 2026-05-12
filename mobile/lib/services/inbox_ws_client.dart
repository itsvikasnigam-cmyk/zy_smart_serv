import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/app_config.dart';
import '../models/user_model.dart';
import '../models/ws_envelope.dart';

typedef WsListener = void Function(WsEnvelope envelope);

/// Thin wrapper around `web_socket_channel` for `client_api` `/ws`.
class InboxWsClient {
  InboxWsClient(this.config);

  final AppConfig config;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;

  Future<void> connect({
    required String token,
    required UserModel user,
    String? superClientId,
    required WsListener onMessage,
    void Function(Object error)? onError,
    void Function()? onDone,
  }) async {
    await disconnect();
    final cid = user.isSuperAdmin ? superClientId : null;
    if (user.isSuperAdmin && (cid == null || cid.isEmpty)) {
      onError?.call(StateError('WebSocket: super_admin needs client_id'));
      return;
    }
    final uri = config.websocketUri(token: token, clientId: cid);
    final ch = WebSocketChannel.connect(uri);
    _channel = ch;
    _sub = ch.stream.listen(
      (raw) {
        if (raw is String) {
          try {
            final map = jsonDecode(raw) as Map<String, dynamic>;
            onMessage(WsEnvelope.fromJson(map));
          } catch (e) {
            onError?.call(e);
          }
        }
      },
      onError: onError,
      onDone: onDone,
      cancelOnError: false,
    );
  }

  void sendPing() {
    _channel?.sink.add(jsonEncode({'type': 'ping'}));
  }

  Future<void> disconnect() async {
    await _sub?.cancel();
    _sub = null;
    await _channel?.sink.close();
    _channel = null;
  }
}
