class RuntimeConfigEntry {
  RuntimeConfigEntry({
    required this.key,
    required this.valueJson,
    this.updatedAt,
  });

  factory RuntimeConfigEntry.fromJson(Map<String, dynamic> json) {
    return RuntimeConfigEntry(
      key: json['key'] as String,
      valueJson: json['value_json'],
      updatedAt: json['updated_at'] as String?,
    );
  }

  final String key;
  final Object? valueJson;
  final String? updatedAt;
}
