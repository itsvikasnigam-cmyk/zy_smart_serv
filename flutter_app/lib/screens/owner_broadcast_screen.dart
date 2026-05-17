import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/broadcast_models.dart';
import '../models/user_model.dart';
import '../state/session_controller.dart';

/// Owner: marketing opt-in + template campaigns (`/broadcast/*` on client_api).
class OwnerBroadcastScreen extends StatefulWidget {
  const OwnerBroadcastScreen({super.key});

  @override
  State<OwnerBroadcastScreen> createState() => _OwnerBroadcastScreenState();
}

class _OwnerBroadcastScreenState extends State<OwnerBroadcastScreen> {
  final _phone = TextEditingController();
  final _waNumberId = TextEditingController();
  final _templateName = TextEditingController();
  final _templateLang = TextEditingController(text: 'en_US');
  final _chatIds = TextEditingController();

  List<MarketingOptIn>? _optIns;
  List<BroadcastCampaign>? _campaigns;
  String? _error;
  bool _loading = false;

  @override
  void dispose() {
    _phone.dispose();
    _waNumberId.dispose();
    _templateName.dispose();
    _templateLang.dispose();
    _chatIds.dispose();
    super.dispose();
  }

  bool _isOwner(UserModel user) => user.role == 'owner';

  Future<void> _load() async {
    final session = context.read<SessionController>();
    final token = session.token;
    final user = session.user;
    if (token == null || user == null || !_isOwner(user)) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final opt = await session.api.listBroadcastOptIn(token: token, user: user);
      final camps = await session.api.listBroadcastCampaigns(token: token, user: user);
      if (!mounted) return;
      setState(() {
        _optIns = opt;
        _campaigns = camps;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _saveOptIn(bool optedIn) async {
    final phone = _phone.text.trim();
    if (phone.isEmpty) {
      setState(() => _error = 'Enter customer phone (E.164, e.g. +9198…).');
      return;
    }
    final session = context.read<SessionController>();
    final token = session.token;
    final user = session.user;
    if (token == null || user == null) return;
    try {
      await session.api.putBroadcastOptIn(
        token: token,
        user: user,
        customerPhoneE164: phone,
        optedIn: optedIn,
        source: 'flutter_owner',
      );
      _phone.clear();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Opt-in ${optedIn ? "on" : "off"}')),
        );
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _createCampaign() async {
    final session = context.read<SessionController>();
    final token = session.token;
    final user = session.user;
    if (token == null || user == null) return;
    final ids = _chatIds.text
        .split(RegExp(r'[\s,]+'))
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    if (ids.isEmpty) {
      setState(() => _error = 'Enter at least one inbox chat_id (from Inbox list).');
      return;
    }
    try {
      await session.api.createBroadcastCampaign(
        token: token,
        user: user,
        fromWaNumberId: _waNumberId.text.trim(),
        templateName: _templateName.text.trim(),
        templateLanguage: _templateLang.text.trim(),
        targetChatIds: ids,
      );
      _chatIds.clear();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Campaign queued (worker sends templates)')),
        );
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final user = context.watch<SessionController>().user;
    if (user == null || !_isOwner(user)) {
      return Scaffold(
        appBar: AppBar(title: const Text('Broadcast')),
        body: const Center(child: Text('Owner login required.')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Broadcast'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Template-only WhatsApp campaigns. Trial/Starter plans may be blocked by policy.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          Text('Client: ${user.clientId ?? "—"}', style: theme.textTheme.labelLarge),
          if (_loading) const LinearProgressIndicator(),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('Marketing opt-in', style: theme.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _phone,
                    decoration: const InputDecoration(
                      labelText: 'Customer phone (E.164)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      FilledButton(
                        onPressed: () => _saveOptIn(true),
                        child: const Text('Opt in'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: () => _saveOptIn(false),
                        child: const Text('Opt out'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('New campaign', style: theme.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _waNumberId,
                    decoration: const InputDecoration(
                      labelText: 'from_wa_number_id (UUID)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _templateName,
                    decoration: const InputDecoration(
                      labelText: 'template_name',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _templateLang,
                    decoration: const InputDecoration(
                      labelText: 'template_language',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _chatIds,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'target_chat_ids (comma-separated)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  FilledButton(
                    onPressed: _createCampaign,
                    child: const Text('Queue campaign'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text('Opt-ins (${_optIns?.length ?? 0})', style: theme.textTheme.titleMedium),
          if (_optIns != null)
            ..._optIns!.map(
              (o) => ListTile(
                title: Text(o.customerPhoneE164),
                subtitle: Text('${o.optedIn ? "opted in" : "opted out"} · ${o.source ?? "—"}'),
              ),
            ),
          const SizedBox(height: 12),
          Text('Campaigns (${_campaigns?.length ?? 0})', style: theme.textTheme.titleMedium),
          if (_campaigns != null)
            ..._campaigns!.map(
              (c) => ListTile(
                title: Text('${c.templateName} · ${c.status}'),
                subtitle: Text('${c.targetCount} targets · ${c.createdAt}'),
              ),
            ),
        ],
      ),
    );
  }
}
