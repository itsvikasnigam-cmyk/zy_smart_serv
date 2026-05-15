class ChatListItem {
  const ChatListItem({
    required this.id,
    required this.clientId,
    required this.customerPhone,
    required this.state,
    this.assignedAgentId,
    this.lastCustomerMsgAt,
    this.lastOutboundAt,
    required this.createdAt,
    this.lastMessagePreview,
    this.aiPausedUntil,
  });

  final String id;
  final String clientId;
  final String customerPhone;
  final String state;
  final String? assignedAgentId;
  final DateTime? lastCustomerMsgAt;
  final DateTime? lastOutboundAt;
  final DateTime createdAt;
  final String? lastMessagePreview;
  /// When set, AI auto-replies are deferred until this instant (UTC from API).
  final DateTime? aiPausedUntil;

  factory ChatListItem.fromJson(Map<String, dynamic> json) {
    return ChatListItem(
      id: json['id'] as String,
      clientId: json['client_id'] as String,
      customerPhone: json['customer_phone'] as String,
      state: json['state'] as String,
      assignedAgentId: json['assigned_agent_id'] as String?,
      lastCustomerMsgAt: _parseDt(json['last_customer_msg_at']),
      lastOutboundAt: _parseDt(json['last_outbound_at']),
      createdAt: DateTime.parse(json['created_at'] as String),
      lastMessagePreview: json['last_message_preview'] as String?,
      aiPausedUntil: _parseDt(json['ai_paused_until']),
    );
  }

  static DateTime? _parseDt(Object? v) {
    if (v == null) return null;
    return DateTime.tryParse(v as String);
  }
}

class InboxNotification {
  const InboxNotification({
    required this.id,
    required this.clientId,
    required this.recipientUserId,
    this.chatId,
    required this.kind,
    required this.title,
    this.body,
    required this.payload,
    this.readAt,
    required this.createdAt,
  });

  final String id;
  final String clientId;
  final String recipientUserId;
  final String? chatId;
  final String kind;
  final String title;
  final String? body;
  final Map<String, dynamic> payload;
  final DateTime? readAt;
  final DateTime createdAt;

  factory InboxNotification.fromJson(Map<String, dynamic> json) {
    final raw = json['payload'];
    final Map<String, dynamic> payload;
    if (raw is Map<String, dynamic>) {
      payload = raw;
    } else if (raw is Map) {
      payload = Map<String, dynamic>.from(raw);
    } else {
      payload = const {};
    }
    return InboxNotification(
      id: json['id'] as String,
      clientId: json['client_id'] as String,
      recipientUserId: json['recipient_user_id'] as String,
      chatId: json['chat_id'] as String?,
      kind: json['kind'] as String,
      title: json['title'] as String,
      body: json['body'] as String?,
      payload: payload,
      readAt: ChatListItem._parseDt(json['read_at']),
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

class InboxMessage {
  const InboxMessage({
    required this.id,
    required this.chatId,
    required this.direction,
    required this.sender,
    required this.text,
    required this.timestamp,
    this.metaMsgId,
    this.source,
    this.outboxStatus,
    this.outboxKind,
  });

  final String id;
  final String chatId;
  final String direction;
  final String sender;
  final String text;
  final DateTime timestamp;
  final String? metaMsgId;
  final String? source;
  final String? outboxStatus;
  final String? outboxKind;

  factory InboxMessage.fromJson(Map<String, dynamic> json) {
    return InboxMessage(
      id: json['id'] as String,
      chatId: json['chat_id'] as String,
      direction: json['direction'] as String,
      sender: json['sender'] as String,
      text: json['text'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      metaMsgId: json['meta_msg_id'] as String?,
      source: json['source'] as String?,
      outboxStatus: json['outbox_status'] as String?,
      outboxKind: json['outbox_kind'] as String?,
    );
  }
}

class ChatDetail {
  const ChatDetail({
    required this.chat,
    this.assignment,
    required this.messages,
    required this.pendingOutbound,
  });

  final ChatListItem chat;
  final Map<String, dynamic>? assignment;
  final List<InboxMessage> messages;
  final List<InboxMessage> pendingOutbound;

  factory ChatDetail.fromJson(Map<String, dynamic> json) {
    return ChatDetail(
      chat: ChatListItem.fromJson(json['chat'] as Map<String, dynamic>),
      assignment: json['assignment'] as Map<String, dynamic>?,
      messages: (json['messages'] as List<dynamic>)
          .map((e) => InboxMessage.fromJson(e as Map<String, dynamic>))
          .toList(),
      pendingOutbound: (json['pending_outbound'] as List<dynamic>? ?? const [])
          .map((e) => InboxMessage.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
