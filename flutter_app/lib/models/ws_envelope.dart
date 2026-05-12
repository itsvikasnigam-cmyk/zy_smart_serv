class WsEnvelope {
  const WsEnvelope({
    required this.event,
    required this.data,
    required this.ts,
  });

  final String event;
  final Map<String, dynamic> data;
  final String ts;

  factory WsEnvelope.fromJson(Map<String, dynamic> json) {
    return WsEnvelope(
      event: json['event'] as String,
      data: (json['data'] as Map<String, dynamic>?) ?? const <String, dynamic>{},
      ts: json['ts'] as String? ?? '',
    );
  }
}
