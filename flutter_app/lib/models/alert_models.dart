class OpsAlertEvent {
  OpsAlertEvent({
    required this.id,
    required this.alertType,
    required this.severity,
    required this.summary,
    required this.detailJson,
    required this.createdAt,
  });

  final String id;
  final String alertType;
  final String severity;
  final String summary;
  final Map<String, dynamic> detailJson;
  final String createdAt;

  factory OpsAlertEvent.fromJson(Map<String, dynamic> json) {
    return OpsAlertEvent(
      id: json['id'] as String,
      alertType: json['alert_type'] as String,
      severity: json['severity'] as String,
      summary: json['summary'] as String,
      detailJson: (json['detail_json'] as Map<String, dynamic>?) ?? {},
      createdAt: json['created_at']?.toString() ?? '',
    );
  }
}

class OpsAlertListPage {
  OpsAlertListPage({required this.items, this.nextCursor});

  final List<OpsAlertEvent> items;
  final String? nextCursor;

  factory OpsAlertListPage.fromJson(Map<String, dynamic> json) {
    final list = json['items'] as List<dynamic>? ?? [];
    return OpsAlertListPage(
      items: list
          .map((e) => OpsAlertEvent.fromJson(e as Map<String, dynamic>))
          .toList(),
      nextCursor: json['next_cursor'] as String?,
    );
  }
}
