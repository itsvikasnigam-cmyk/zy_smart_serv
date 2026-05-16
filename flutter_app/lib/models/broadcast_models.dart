class MarketingOptIn {
  MarketingOptIn({
    required this.clientId,
    required this.customerPhoneE164,
    required this.optedIn,
    this.source,
    this.updatedAt,
  });

  final String clientId;
  final String customerPhoneE164;
  final bool optedIn;
  final String? source;
  final String? updatedAt;

  factory MarketingOptIn.fromJson(Map<String, dynamic> json) {
    return MarketingOptIn(
      clientId: json['client_id'] as String,
      customerPhoneE164: json['customer_phone_e164'] as String,
      optedIn: json['opted_in'] as bool,
      source: json['source'] as String?,
      updatedAt: json['updated_at'] as String?,
    );
  }
}

class BroadcastCampaign {
  BroadcastCampaign({
    required this.id,
    required this.clientId,
    required this.fromWaNumberId,
    required this.templateName,
    required this.templateLanguage,
    required this.status,
    required this.createdAt,
    required this.targetCount,
  });

  final String id;
  final String clientId;
  final String fromWaNumberId;
  final String templateName;
  final String templateLanguage;
  final String status;
  final String createdAt;
  final int targetCount;

  factory BroadcastCampaign.fromJson(Map<String, dynamic> json) {
    return BroadcastCampaign(
      id: json['id'] as String,
      clientId: json['client_id'] as String,
      fromWaNumberId: json['from_wa_number_id'] as String,
      templateName: json['template_name'] as String,
      templateLanguage: json['template_language'] as String,
      status: json['status'] as String,
      createdAt: json['created_at'] as String,
      targetCount: (json['target_count'] as num?)?.toInt() ?? 0,
    );
  }
}
