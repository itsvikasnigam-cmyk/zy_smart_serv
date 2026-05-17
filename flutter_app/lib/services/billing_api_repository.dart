import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/billing_api_config.dart';
import '../models/user_model.dart';
import 'client_api_repository.dart';

class BillingApiRepository {
  BillingApiRepository(this.config);

  BillingApiConfig config;

  Map<String, String> _headers(String token) {
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  Map<String, String>? _clientQuery(String? role, String? superClientId) {
    if (role == 'super_admin') {
      if (superClientId == null || superClientId.isEmpty) {
        throw StateError('super_admin needs client_id for billing');
      }
      return {'client_id': superClientId};
    }
    return null;
  }

  Future<Map<String, dynamic>> getSubscription({
    required String token,
    required UserModel user,
    String? superClientId,
  }) async {
    final q = _clientQuery(user.role, superClientId);
    final uri = config.rest('/billing/subscription', q);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode == 401) {
      throw ApiUnauthorizedException();
    }
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getInvoices({
    required String token,
    required UserModel user,
    String? superClientId,
    int limit = 20,
  }) async {
    final q = <String, String>{'limit': '$limit'};
    final extra = _clientQuery(user.role, superClientId);
    if (extra != null) {
      q.addAll(extra);
    }
    final uri = config.rest('/billing/invoices', q);
    final res = await http.get(uri, headers: _headers(token));
    if (res.statusCode == 401) {
      throw ApiUnauthorizedException();
    }
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    final map = jsonDecode(res.body) as Map<String, dynamic>;
    final list = map['invoices'] as List<dynamic>? ?? [];
    return list.map((e) => e as Map<String, dynamic>).toList();
  }

  Future<Map<String, dynamic>> createRazorpayCheckout({
    required String token,
    required UserModel user,
    required int amountPaise,
    String? superClientId,
    String currency = 'INR',
  }) async {
    final uri = config.rest('/billing/razorpay/create-checkout', _clientQuery(user.role, superClientId));
    final res = await http.post(
      uri,
      headers: _headers(token),
      body: jsonEncode({
        'amount_paise': amountPaise,
        'currency': currency,
        'notes': <String, String>{},
      }),
    );
    if (res.statusCode == 401) {
      throw ApiUnauthorizedException();
    }
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, res.body);
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
