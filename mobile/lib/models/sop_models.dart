class SopSummary {
  SopSummary({
    required this.id,
    required this.title,
    required this.slug,
    required this.category,
    required this.status,
    required this.currentVersion,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String title;
  final String slug;
  final String? category;
  final String status;
  final int currentVersion;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory SopSummary.fromJson(Map<String, dynamic> j) {
    return SopSummary(
      id: j['id'] as String,
      title: j['title'] as String,
      slug: j['slug'] as String,
      category: j['category'] as String?,
      status: j['status'] as String,
      currentVersion: (j['current_version'] as num).toInt(),
      createdAt: DateTime.parse(j['created_at'] as String),
      updatedAt: DateTime.parse(j['updated_at'] as String),
    );
  }
}

class SopDetail extends SopSummary {
  SopDetail({
    required super.id,
    required super.title,
    required super.slug,
    required super.category,
    required super.status,
    required super.currentVersion,
    required super.createdAt,
    required super.updatedAt,
    required this.bodyMarkdown,
  });

  final String bodyMarkdown;

  factory SopDetail.fromJson(Map<String, dynamic> j) {
    return SopDetail(
      id: j['id'] as String,
      title: j['title'] as String,
      slug: j['slug'] as String,
      category: j['category'] as String?,
      status: j['status'] as String,
      currentVersion: (j['current_version'] as num).toInt(),
      createdAt: DateTime.parse(j['created_at'] as String),
      updatedAt: DateTime.parse(j['updated_at'] as String),
      bodyMarkdown: j['body_markdown'] as String,
    );
  }
}

class SopVersion {
  SopVersion({
    required this.versionNum,
    required this.bodyMarkdown,
    required this.createdAt,
    required this.createdByUserId,
  });

  final int versionNum;
  final String bodyMarkdown;
  final DateTime createdAt;
  final String? createdByUserId;

  factory SopVersion.fromJson(Map<String, dynamic> j) {
    return SopVersion(
      versionNum: (j['version_num'] as num).toInt(),
      bodyMarkdown: j['body_markdown'] as String,
      createdAt: DateTime.parse(j['created_at'] as String),
      createdByUserId: j['created_by_user_id'] as String?,
    );
  }
}

class SopCreateResponse {
  SopCreateResponse({required this.id, required this.currentVersion});

  final String id;
  final int currentVersion;

  factory SopCreateResponse.fromJson(Map<String, dynamic> j) {
    return SopCreateResponse(
      id: j['id'] as String,
      currentVersion: (j['current_version'] as num).toInt(),
    );
  }
}

class RunStartResult {
  RunStartResult({
    required this.id,
    required this.sopId,
    required this.sopVersionAtRun,
  });

  final String id;
  final String sopId;
  final int sopVersionAtRun;

  factory RunStartResult.fromJson(Map<String, dynamic> j) {
    return RunStartResult(
      id: j['id'] as String,
      sopId: j['sop_id'] as String,
      sopVersionAtRun: (j['sop_version_at_run'] as num).toInt(),
    );
  }
}

class RunLog {
  RunLog({
    required this.id,
    required this.sopId,
    required this.sopVersionAtRun,
    required this.contextJson,
    required this.triggerType,
    required this.createdByUserId,
    required this.clientId,
    required this.createdAt,
  });

  final String id;
  final String sopId;
  final int sopVersionAtRun;
  final Map<String, dynamic> contextJson;
  final String triggerType;
  final String? createdByUserId;
  final String? clientId;
  final DateTime createdAt;

  factory RunLog.fromJson(Map<String, dynamic> j) {
    final ctx = j['context_json'];
    return RunLog(
      id: j['id'] as String,
      sopId: j['sop_id'] as String,
      sopVersionAtRun: (j['sop_version_at_run'] as num).toInt(),
      contextJson: ctx is Map<String, dynamic>
          ? Map<String, dynamic>.from(ctx)
          : <String, dynamic>{},
      triggerType: j['trigger_type'] as String,
      createdByUserId: j['created_by_user_id'] as String?,
      clientId: j['client_id'] as String?,
      createdAt: DateTime.parse(j['created_at'] as String),
    );
  }
}
