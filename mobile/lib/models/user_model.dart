class UserModel {
  const UserModel({
    required this.id,
    required this.role,
    this.clientId,
    this.name,
    this.email,
  });

  final String id;
  final String role;
  final String? clientId;
  final String? name;
  final String? email;

  bool get isSuperAdmin => role == 'super_admin';
  bool get isOwner => role == 'owner';
  bool get isAgent => role == 'agent';

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String,
      role: json['role'] as String,
      clientId: json['client_id'] as String?,
      name: json['name'] as String?,
      email: json['email'] as String?,
    );
  }
}
