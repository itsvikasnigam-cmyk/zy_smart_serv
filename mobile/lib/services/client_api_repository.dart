import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../models/chat_models.dart';
import '../models/user_model.dart';

class ApiException implements Exception {
  ApiException(this.statusCode, this.body);
  final int statusCode;
  final String body;

  @override
  String toString() => 'ApiException($statusCode): $body';
}

/// Session expired for authenticated `client_api` calls.
class ApiUnauthorizedException implements Exception {
  @override
  String toString() => 'Unauthorized — please sign in again.';
}

class ClientApiRepository {
  ClientApiRepository(this.config);

  AppConfig config;

  Map<String, String> _headers(String? token) {
    final h = <String, String>{'Content-Type': 'application/json'};
    if (token != null && token.isNotEmpty) {
      h['Authorization'] = 'Bearer $token';
    }
    return h;
  }

  Map<String, String>? _clientQuery(String? role, String? superClientId) {
    if (role == 'super_admin') {
      if (superClientId == null || superClientId.isEmpty) {
        throw StateError('super_admin requires a client_id scope');
      }
      return {'client_id': superClientId};
    }
    return null;
  }

  Future<({String token, UserModel user})> login({
    required String email,
    required String password,
  }) async {
    final uri = config.rest('/auth/login');
    final res = await http.post(
      uri,
      headers: _headers(null),
      body: jsonEncode({'email': email, 'password': password}),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final map = jsonDecode(res.body) as Map<String, dynamic>;
    final token = map['access_token'] as String;
    final user = UserModel.fromJson(map['user'] as Map<String, dynamic>);
    return (token: token, user: user);
  }

  Future<UserModel> me(String token) async {
    final uri = config.rest('/auth/me');
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    return UserModel.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<List<UserModel>> listUsers({
    required String token,
    required UserModel user,
    String? role,
    String? superClientId,
  }) async {
    final q = <String, String>{};
    if (role != null && role.isNotEmpty) {
      q['role'] = role;
    }
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }

    final uri = config.rest('/users', q.isEmpty ? null : q);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => UserModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<ChatListItem>> listChats({
    required String token,
    required UserModel user,
    String? superClientId,
    int limit = 50,
    String? state,
    String? assigned,
    String? phoneQuery,
  }) async {
    final q = <String, String>{'limit': '$limit'};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }
    if (state != null && state.isNotEmpty) {
      q['state'] = state;
    }
    if (assigned != null && assigned.isNotEmpty) {
      q['assigned'] = assigned;
    }
    if (phoneQuery != null && phoneQuery.trim().isNotEmpty) {
      q['q'] = phoneQuery.trim();
    }

    final uri = config.rest('/inbox/chats', q);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final map = jsonDecode(res.body) as Map<String, dynamic>;
    final items = map['items'] as List<dynamic>;
    return items.map((e) => ChatListItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ChatDetail> chatDetail({
    required String token,
    required UserModel user,
    required String chatId,
    String? superClientId,
  }) async {
    final q = <String, String>{};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }

    final uri = config.rest('/inbox/chats/$chatId', q.isEmpty ? null : q);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    return ChatDetail.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<void> postAssign({
    required String token,
    required UserModel user,
    required String chatId,
    required String assigneeUserId,
    String? superClientId,
  }) async {
    final q = <String, String>{};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }
    final uri = config.rest('/inbox/chats/$chatId/assign', q.isEmpty ? null : q);
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode({'user_id': assigneeUserId}),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  Future<void> postReply({
    required String token,
    required UserModel user,
    required String chatId,
    required String text,
    String? superClientId,
  }) async {
    final q = <String, String>{};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }

    final uri = config.rest('/inbox/chats/$chatId/reply', q.isEmpty ? null : q);
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode({'text': text}),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  Future<void> postReassign({
    required String token,
    required UserModel user,
    required String chatId,
    required String assigneeUserId,
    String? superClientId,
  }) async {
    final q = <String, String>{};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }
    final uri = config.rest('/inbox/chats/$chatId/reassign', q.isEmpty ? null : q);
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode({'user_id': assigneeUserId}),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  Future<void> postUnassign({
    required String token,
    required UserModel user,
    required String chatId,
    String? superClientId,
    String? reason,
  }) async {
    final q = <String, String>{};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }
    final uri = config.rest('/inbox/chats/$chatId/unassign', q.isEmpty ? null : q);
    final body = <String, dynamic>{};
    if (reason != null && reason.isNotEmpty) {
      body['reason'] = reason;
    }
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode(body),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  Future<void> postEscalate({
    required String token,
    required UserModel user,
    required String chatId,
    String? superClientId,
    String? toUserId,
    String? reason,
  }) async {
    final q = <String, String>{};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }
    final uri = config.rest('/inbox/chats/$chatId/escalate', q.isEmpty ? null : q);
    final body = <String, dynamic>{};
    if (toUserId != null && toUserId.isNotEmpty) {
      body['to_user_id'] = toUserId;
    }
    if (reason != null && reason.isNotEmpty) {
      body['reason'] = reason;
    }
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode(body),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  Future<void> postTyping({
    required String token,
    required UserModel user,
    required String chatId,
    required String state,
    String? superClientId,
    int ttlSeconds = 8,
  }) async {
    final q = <String, String>{};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }

    final uri = config.rest('/inbox/chats/$chatId/typing', q.isEmpty ? null : q);
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode({'state': state, 'ttl_seconds': ttlSeconds}),
    );
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
  }

  Future<Map<String, dynamic>> dashGet(String token, String path) async {
    final uri = config.rest(path);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode == 401) {
      throw ApiUnauthorizedException();
    }
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final decoded = jsonDecode(res.body);
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    return <String, dynamic>{'value': decoded};
  }
}
