import 'package:flutter/foundation.dart';

import '../config/app_config.dart';
import '../config/billing_api_config.dart';
import '../config/ops_api_config.dart';
import '../models/user_model.dart';
import '../models/ws_envelope.dart';
import '../services/billing_api_repository.dart';
import '../services/client_api_repository.dart';
import '../services/inbox_ws_client.dart';
import '../services/local_settings_store.dart';
import '../services/ops_api_repository.dart';

const _kBaseUrl = 'client_api_base_url';
const _kOpsBaseUrl = 'ops_api_base_url';
const _kSuperClientId = 'super_admin_client_id';

class SessionController extends ChangeNotifier {
  SessionController() {
    _repo = ClientApiRepository(_config);
    _opsRepo = OpsApiRepository(_opsConfig);
    _billingRepo = BillingApiRepository(_billingConfig);
    _ws = InboxWsClient(_config);
  }

  AppConfig _config = AppConfig();
  OpsApiConfig _opsConfig = OpsApiConfig();
  BillingApiConfig _billingConfig = BillingApiConfig();
  late ClientApiRepository _repo;
  late OpsApiRepository _opsRepo;
  late BillingApiRepository _billingRepo;
  late InboxWsClient _ws;

  String? _token;
  UserModel? _user;
  String _superAdminClientId = '';

  bool _busy = false;
  String? _error;
  bool _wsConnected = false;
  String? _wsLastError;
  final List<String> _wsRecent = [];

  String? get token => _token;
  UserModel? get user => _user;
  String get superAdminClientId => _superAdminClientId;
  AppConfig get config => _config;
  OpsApiConfig get opsConfig => _opsConfig;
  BillingApiConfig get billingConfig => _billingConfig;
  ClientApiRepository get api => _repo;
  OpsApiRepository get opsApi => _opsRepo;
  BillingApiRepository get billingApi => _billingRepo;
  InboxWsClient get ws => _ws;
  bool get busy => _busy;
  String? get lastError => _error;
  bool get isLoggedIn => _token != null && _user != null;
  bool get wsConnected => _wsConnected;
  String? get wsLastError => _wsLastError;
  List<String> get wsRecentLines => List.unmodifiable(_wsRecent);

  /// Owner and agent use tenant-scoped inbox + WebSocket without extra scope.
  bool get usesTenantInbox =>
      _user != null && (_user!.isOwner || _user!.isAgent);

  Future<void> loadPersistedSettings() async {
    final m = await LocalSettingsStore.readAll();
    final saved = m[_kBaseUrl];
    if (saved != null && saved.isNotEmpty) {
      setBaseUrl(saved, persist: false);
    }
    final opsSaved = m[_kOpsBaseUrl];
    if (opsSaved != null && opsSaved.isNotEmpty) {
      setOpsBaseUrl(opsSaved, persist: false);
    }
    final cid = m[_kSuperClientId];
    if (cid != null && cid.isNotEmpty) {
      _superAdminClientId = cid;
    }
    notifyListeners();
  }

  Future<void> _persistDisk() async {
    try {
      await LocalSettingsStore.writeAll({
        _kBaseUrl: _config.apiBaseUrl,
        _kOpsBaseUrl: _opsConfig.apiBaseUrl,
        if (_superAdminClientId.isNotEmpty) _kSuperClientId: _superAdminClientId,
      });
    } catch (e, st) {
      if (kDebugMode) {
        // ignore: avoid_print
        print('LocalSettingsStore write failed: $e $st');
      }
    }
  }

  void setBaseUrl(String url, {bool persist = true}) {
    _config = AppConfig(baseUrl: url);
    _repo = ClientApiRepository(_config);
    _ws = InboxWsClient(_config);
    if (persist) {
      unawaited(_persistDisk());
    }
    notifyListeners();
  }

  void setSuperAdminClientId(String clientId, {bool persist = true}) {
    _superAdminClientId = clientId.trim();
    if (persist) {
      unawaited(_persistDisk());
    }
    notifyListeners();
  }

  void setOpsBaseUrl(String url, {bool persist = true}) {
    _opsConfig = OpsApiConfig(baseUrl: url);
    _opsRepo = OpsApiRepository(_opsConfig);
    if (persist) {
      unawaited(_persistDisk());
    }
    notifyListeners();
  }

  Future<void> login(String email, String password) async {
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      final r = await _repo.login(email: email, password: password);
      _token = r.token;
      final me = await _repo.me(_token!);
      if (!me.isOwner && !me.isAgent && !me.isSuperAdmin) {
        _token = null;
        _user = null;
        _busy = false;
        _error = 'Unsupported account role: ${me.role}. Use owner, agent, or super_admin.';
        notifyListeners();
        throw StateError(_error!);
      }
      _user = me;
      _busy = false;
      notifyListeners();
    } catch (e) {
      _busy = false;
      _error = e.toString();
      notifyListeners();
      rethrow;
    }
  }

  void logout() {
    _token = null;
    _user = null;
    _wsConnected = false;
    _wsLastError = null;
    _wsRecent.clear();
    unawaited(_ws.disconnect());
    notifyListeners();
  }

  Future<void> refreshMe() async {
    if (_token == null) return;
    _user = await _repo.me(_token!);
    notifyListeners();
  }

  void _logWs(String line) {
    _wsRecent.insert(0, line);
    if (_wsRecent.length > 40) {
      _wsRecent.removeRange(40, _wsRecent.length);
    }
    notifyListeners();
  }

  Future<void> connectWebSocket() async {
    if (!isLoggedIn || _token == null || _user == null) return;
    if (_user!.isSuperAdmin) {
      return;
    }

    await _ws.disconnect();
    _wsConnected = false;
    _wsLastError = null;
    notifyListeners();

    try {
      await _ws.connect(
        token: _token!,
        user: _user!,
        superClientId: null,
        onMessage: (WsEnvelope env) {
          _logWs('${env.event} @ ${env.ts}');
          if (env.event == 'message_new' ||
              env.event == 'assignment_changed' ||
              env.event == 'chat_state_changed') {
            bumpInboxGeneration();
          } else if (env.event == 'notification') {
            bumpInboxGeneration();
            bumpNotificationsGeneration();
            unawaited(refreshUnreadNotificationCount());
          } else {
            notifyListeners();
          }
        },
        onError: (e) {
          _logWs('error: $e');
          _wsLastError = e.toString();
          _wsConnected = false;
          notifyListeners();
        },
        onDone: () {
          _wsConnected = false;
          _logWs('socket closed');
          notifyListeners();
        },
      );
      _wsConnected = true;
      _wsLastError = null;
      _logWs('connected');
      notifyListeners();
    } catch (e, st) {
      _wsConnected = false;
      _wsLastError = e.toString();
      if (kDebugMode) {
        // ignore: avoid_print
        print('WebSocket connect failed: $e $st');
      }
      notifyListeners();
    }
  }

  Future<void> disconnectWebSocket() async {
    await _ws.disconnect();
    _wsConnected = false;
    _wsLastError = null;
    notifyListeners();
  }

  int _inboxGeneration = 0;
  int get inboxGeneration => _inboxGeneration;

  void bumpInboxGeneration() {
    _inboxGeneration++;
    notifyListeners();
  }

  int _notificationsGeneration = 0;
  int get notificationsGeneration => _notificationsGeneration;

  void bumpNotificationsGeneration() {
    _notificationsGeneration++;
    notifyListeners();
  }

  int _unreadNotificationCount = 0;
  int get unreadNotificationCount => _unreadNotificationCount;

  Future<void> refreshUnreadNotificationCount() async {
    if (!isLoggedIn || _token == null || _user == null) return;
    if (_user!.isSuperAdmin) {
      _unreadNotificationCount = 0;
      notifyListeners();
      return;
    }
    try {
      final list = await _repo.listNotifications(
        token: _token!,
        user: _user!,
        unreadOnly: true,
        limit: 200,
      );
      _unreadNotificationCount = list.length;
      notifyListeners();
    } catch (_) {
      // Keep last count on transient errors.
    }
  }

  int _dashGeneration = 0;
  int get dashGeneration => _dashGeneration;

  void bumpDashGeneration() {
    _dashGeneration++;
    notifyListeners();
  }
}

void unawaited(Future<void> f) {
  f.catchError((Object e, StackTrace st) {
    if (kDebugMode) {
      // ignore: avoid_print
      print('unawaited error: $e $st');
    }
  });
}
