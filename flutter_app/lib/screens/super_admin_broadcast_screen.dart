import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/broadcast_models.dart';
import '../state/session_controller.dart';

/// M6: marketing opt-in + template campaign queue (`client_api` `/broadcast/*`).
class SuperAdminBroadcastScreen extends StatefulWidget {
  const SuperAdminBroadcastScreen({super.key});

  @override
  State<SuperAdminBroadcastScreen> createState() =>
      _SuperAdminBroadcastScreenState();
}

class _SuperAdminBroadcastScreenState extends State<SuperAdminBroadcastScreen> {
  final _clientId = TextEditingController();
  final _phone = TextEditingController();
  final _waNumberId = TextEditingController();
  final _templateName = TextEditingController();
  final _templateLang = TextEditingController(text: 'en_US');
  final _chatIds = TextEditingController();

  List<MarketingOptIn>? _optIns;
  List<BroadcastCampaign>? _campaigns;
  String? _error;
  bool _loading = false;

  void _syncClientIdFromSession(SessionController session) {
    if (_clientId.text.trim().isEmpty && session.superAdminClientId.isNotEmpty) {
      _clientId.text = session.superAdminClientId;
    }
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _syncClientIdFromSession(context.read<SessionController>());
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _clientId.dispose();
    _phone.dispose();
    _waNumberId.dispose();
    _templateName.dispose();
    _templateLang.dispose();
    _chatIds.dispose();
    super.dispose();
  }

  String? _requireClientId() {
    final session = context.read<SessionController>();
    var cid = _clientId.text.trim();
    if (cid.isEmpty) {
      cid = session.superAdminClientId.trim();
      if (cid.isNotEmpty) {
        _clientId.text = cid;
      }
    }
    if (cid.isEmpty) {
      setState(() => _error =
          'Enter tenant client_id (UUID) above, or set it under the link icon '
          '(API settings) and tap Load again.');
      return null;
    }
    session.setSuperAdminClientId(cid);
    return cid;
  }

  Future<void> _load() async {
    final cid = _requireClientId();
    if (cid == null) return;
    final session = context.read<SessionController>();
    final token = session.token;
    final user = session.user;
    if (token == null || user == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final opt = await session.api.listBroadcastOptIn(
        token: token,
        user: user,
        superClientId: cid,
      );
      final camps = await session.api.listBroadcastCampaigns(
        token: token,
        user: user,
        superClientId: cid,
      );
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
    final cid = _requireClientId();
    if (cid == null) return;
    final phone = _phone.text.trim();
    if (phone.isEmpty) {
      setState(() => _error = 'Enter customer phone (E.164).');
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
        superClientId: cid,
        customerPhoneE164: phone,
        optedIn: optedIn,
        source: 'flutter_super_admin',
      );
      _phone.clear();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Opt-in ${optedIn ? "enabled" : "disabled"}')),
        );
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _createCampaign() async {
    final cid = _requireClientId();
    if (cid == null) return;
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
      setState(() => _error = 'Enter at least one inbox chat_id (comma-separated).');
      return;
    }
    try {
      await session.api.createBroadcastCampaign(
        token: token,
        user: user,
        superClientId: cid,
        fromWaNumberId: _waNumberId.text.trim(),
        templateName: _templateName.text.trim(),
        templateLanguage: _templateLang.text.trim(),
        targetChatIds: ids,
      );
      _chatIds.clear();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Campaign queued')),
        );
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final session = context.watch<SessionController>();
    _syncClientIdFromSession(session);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Broadcast (M6)', style: theme.textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          'Template-only WhatsApp campaigns. Worker enforces opt-in and plan gates.',
          style: theme.textTheme.bodySmall,
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _clientId,
          decoration: InputDecoration(
            labelText: 'Tenant client_id (required for super_admin)',
            hintText: session.superAdminClientId.isNotEmpty
                ? session.superAdminClientId
                : 'e.g. 17682c77-1524-4ebd-94e5-958e7f37ac60',
            border: const OutlineInputBorder(),
            helperText: 'Also saved via link icon → API settings',
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            FilledButton(onPressed: _load, child: const Text('Load')),
            if (_loading) ...[
              const SizedBox(width: 12),
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ],
          ],
        ),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
        ],
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
                    labelText: 'customer_phone_e164',
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
                    labelText: 'from_wa_number_id',
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
                    labelText: 'target_chat_ids (comma-separated UUIDs)',
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
              subtitle: Text(
                '${c.targetCount} targets · ${c.templateLanguage}\n${c.createdAt}',
              ),
              isThreeLine: true,
            ),
          ),
      ],
    );
  }
}
