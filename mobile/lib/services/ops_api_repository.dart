import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/ops_api_config.dart';
import '../models/runtime_config_models.dart';
import '../models/sop_models.dart';

class OpsApiException implements Exception {
  OpsApiException(this.statusCode, this.body);
  final int statusCode;
  final String body;

  @override
  String toString() => 'OpsApiException($statusCode): $body';
}

/// JWT rejected or missing — caller should log out (no retry loop).
class OpsApiUnauthorizedException extends OpsApiException {
  OpsApiUnauthorizedException() : super(401, '');
}

/// Role is not super_admin (or ops policy) — show message; do not retry.
class OpsApiForbiddenException extends OpsApiException {
  OpsApiForbiddenException([String body = ''])
      : super(403, body);

  String get userMessage {
    if (body.trim().isEmpty) {
      return 'Access denied: ops_api requires super_admin.';
    }
    return 'Access denied (needs super_admin for this ops_api action).';
  }
}

void _throwForStatus(http.Response res) {
  if (res.statusCode == 401) {
    throw OpsApiUnauthorizedException();
  }
  if (res.statusCode == 403) {
    throw OpsApiForbiddenException(res.body);
  }
}

class OpsApiRepository {
  OpsApiRepository(this.config);

  OpsApiConfig config;

  Map<String, String> _headers(String token) {
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  Future<List<SopSummary>> listSops({
    required String token,
    String? category,
    String? status,
    String? q,
  }) async {
    final qm = <String, String>{};
    if (category != null && category.isNotEmpty) {
      qm['category'] = category;
    }
    if (status != null && status.isNotEmpty) {
      qm['status'] = status;
    }
    if (q != null && q.trim().isNotEmpty) {
      qm['q'] = q.trim();
    }
    final uri = config.rest('/ops/sops', qm.isEmpty ? null : qm);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => SopSummary.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<SopDetail> getSop({required String token, required String sopId}) async {
    final uri = config.rest('/ops/sops/$sopId');
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    return SopDetail.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<List<SopVersion>> listSopVersions({
    required String token,
    required String sopId,
  }) async {
    final uri = config.rest('/ops/sops/$sopId/versions');
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => SopVersion.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<SopCreateResponse> createSop({
    required String token,
    required Map<String, dynamic> body,
  }) async {
    final uri = config.rest('/ops/sops');
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode(body),
    );
    if (res.statusCode != 201) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    return SopCreateResponse.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<SopCreateResponse> updateSop({
    required String token,
    required String sopId,
    required Map<String, dynamic> body,
  }) async {
    final uri = config.rest('/ops/sops/$sopId');
    final res = await http.put(
      uri,
      headers: _headers(token),
      body: jsonEncode(body),
    );
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    return SopCreateResponse.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<RunStartResult> startRun({
    required String token,
    required String sopId,
    required Map<String, dynamic> contextJson,
    String triggerType = 'manual',
    String? clientId,
  }) async {
    final uri = config.rest('/ops/sops/$sopId/run');
    final body = <String, dynamic>{
      'context_json': contextJson,
      'trigger_type': triggerType,
    };
    if (clientId != null && clientId.trim().isNotEmpty) {
      body['client_id'] = clientId.trim();
    }
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode(body),
    );
    if (res.statusCode != 201) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    return RunStartResult.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Lists runs (server caps at 500 rows — use date filters to narrow).
  Future<List<RunLog>> listRuns({
    required String token,
    String? clientId,
    String? sopId,
    String? triggerType,
    String? fromDateYyyyMmDd,
    String? toDateYyyyMmDd,
  }) async {
    final qm = <String, String>{};
    if (clientId != null && clientId.isNotEmpty) {
      qm['client_id'] = clientId;
    }
    if (sopId != null && sopId.isNotEmpty) {
      qm['sop_id'] = sopId;
    }
    if (triggerType != null && triggerType.isNotEmpty) {
      qm['trigger_type'] = triggerType;
    }
    if (fromDateYyyyMmDd != null && fromDateYyyyMmDd.isNotEmpty) {
      qm['from_date'] = fromDateYyyyMmDd;
    }
    if (toDateYyyyMmDd != null && toDateYyyyMmDd.isNotEmpty) {
      qm['to_date'] = toDateYyyyMmDd;
    }
    final uri = config.rest('/ops/runs', qm.isEmpty ? null : qm);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    final decoded = jsonDecode(res.body);
    final List<dynamic> list;
    if (decoded is Map<String, dynamic> && decoded['items'] is List) {
      list = decoded['items'] as List<dynamic>;
    } else if (decoded is List) {
      list = decoded;
    } else {
      throw OpsApiException(res.statusCode, 'unexpected /ops/runs shape');
    }
    return list.map((e) => RunLog.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<RunLog> getRun({required String token, required String runId}) async {
    final uri = config.rest('/ops/runs/$runId');
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    return RunLog.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<RuntimeConfigEntry> getRuntimeConfig({
    required String token,
    required String key,
  }) async {
    final encoded = Uri.encodeComponent(key);
    final uri = config.rest('/ops/runtime-config/$encoded');
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    return RuntimeConfigEntry.fromJson(
      jsonDecode(res.body) as Map<String, dynamic>,
    );
  }

  Future<RuntimeConfigEntry> putRuntimeConfig({
    required String token,
    required String key,
    required Object? valueJson,
    String? reason,
  }) async {
    final encoded = Uri.encodeComponent(key);
    final uri = config.rest('/ops/runtime-config/$encoded');
    final body = jsonEncode({
      'value_json': valueJson,
      if (reason != null && reason.isNotEmpty) 'reason': reason,
    });
    final res = await http.put(uri, headers: _headers(token), body: body);
    if (res.statusCode != 200) {
      _throwForStatus(res);
      throw OpsApiException(res.statusCode, res.body);
    }
    return RuntimeConfigEntry.fromJson(
      jsonDecode(res.body) as Map<String, dynamic>,
    );
  }
}
