import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../services/client_api_repository.dart';
import '../state/session_controller.dart';

/// Owner / agent read-only **Chat J** client aggregates (`GET /dash/client/*`).
class ClientDashboardScreen extends StatefulWidget {
  const ClientDashboardScreen({super.key});

  @override
  State<ClientDashboardScreen> createState() => _ClientDashboardScreenState();
}

/// Shown when `GET /dash/client/*` is not deployed (404) so layout stays usable offline.
const _kMockOverview = <String, dynamic>{
  'business_name': 'Demo client (offline preview)',
  'entitlement_plan': 'starter',
  'billing_provider': null,
  'trial_end': null,
  'wa_numbers_count': 1,
  'chats_by_state': {'AI_ACTIVE': 3, 'PENDING_AGENT': 1, 'AGENT_ACTIVE': 2},
  'usage_today': {
    'inbound_customer_messages': 12,
    'outbound_ai_messages': 8,
    'outbound_agent_messages': 4,
    'outbound_system_messages': 0,
  },
  'messages_last_7d': {'customer': 40, 'ai': 30, 'agent': 15, 'system': 2},
};

const _kMockAgents = <String, dynamic>{
  'agents': [
    {
      'user_id': '00000000-0000-0000-0000-000000000001',
      'name': 'Alex Agent',
      'email': 'agent@example.com',
      'replies_last_7d': 15,
      'active_assigned_chats': 2,
    },
  ],
};

const _kMockQuality = <String, dynamic>{
  'chats_pending_agent': 1,
  'chats_with_handoff_reason_7d': 2,
  'messages_last_7d': {'customer': 40, 'ai': 30, 'agent': 15, 'system': 2},
  'notes': 'Illustrative data only — connect client_api with Chat J routes for live numbers.',
};

class _ClientDashboardScreenState extends State<ClientDashboardScreen> {
  Map<String, dynamic>? _overview;
  Map<String, dynamic>? _agents;
  Map<String, dynamic>? _quality;
  String? _error;
  bool _loading = true;
  bool _usingMock = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadAll());
  }

  Future<void> _loadAll() async {
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _loading = true;
      _error = null;
      _usingMock = false;
    });
    try {
      final o = await session.api.dashGet(token, '/dash/client/overview');
      final a = await session.api.dashGet(token, '/dash/client/agents');
      final q = await session.api.dashGet(token, '/dash/client/quality');
      if (!mounted) return;
      setState(() {
        _overview = o;
        _agents = a;
        _quality = q;
        _loading = false;
        _usingMock = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.statusCode == 404) {
        setState(() {
          _overview = Map<String, dynamic>.from(_kMockOverview);
          _agents = Map<String, dynamic>.from(_kMockAgents);
          _quality = Map<String, dynamic>.from(_kMockQuality);
          _loading = false;
          _usingMock = true;
          _error = null;
        });
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      if (e is ApiUnauthorizedException) {
        session.logout();
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  static String? _str(Object? v) => v == null ? null : v as String?;

  static int _int(Object? v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is num) return v.toInt();
    return int.tryParse('$v') ?? 0;
  }

  static Map<String, dynamic> _map(Object? v) =>
      v is Map<String, dynamic> ? v : <String, dynamic>{};

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dateFmt = DateFormat.yMMMd();

    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(onPressed: _loadAll, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    final ov = _overview ?? const <String, dynamic>{};
    final ag = _agents ?? const <String, dynamic>{};
    final qu = _quality ?? const <String, dynamic>{};
    final usage = _map(ov['usage_today']);
    final msg7 = _map(ov['messages_last_7d']);
    final quMsg7 = _map(qu['messages_last_7d']);
    final chatsByState = _map(ov['chats_by_state']);
    final agentList = (ag['agents'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .toList();

    return RefreshIndicator(
      onRefresh: _loadAll,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_usingMock)
            MaterialBanner(
              content: const Text(
                'Dashboard API returned 404 — showing offline preview. '
                'Deploy client_api with `/dash/client/*` (Chat J) for live data.',
              ),
              actions: [
                TextButton(onPressed: _loadAll, child: const Text('Retry')),
              ],
            ),
          Text('Overview', style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _str(ov['business_name']) ?? '—',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Plan: ${_str(ov['entitlement_plan']) ?? '—'} · '
                    'Billing: ${_str(ov['billing_provider']) ?? '—'}',
                    style: theme.textTheme.bodySmall,
                  ),
                  if (ov['trial_end'] != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      () {
                        final raw = ov['trial_end'].toString();
                        final d = DateTime.tryParse(raw);
                        final label =
                            d != null ? dateFmt.format(d.toLocal()) : raw;
                        return 'Trial ends: $label';
                      }(),
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                  const SizedBox(height: 8),
                  Text('WhatsApp numbers: ${_int(ov['wa_numbers_count'])}'),
                  const SizedBox(height: 12),
                  Text('Chats by state', style: theme.textTheme.labelLarge),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      if (chatsByState.isEmpty)
                        Text('No data', style: theme.textTheme.bodySmall)
                      else
                        for (final e in chatsByState.entries.toList()
                          ..sort((a, b) => a.key.compareTo(b.key)))
                          Chip(label: Text('${e.key}: ${e.value}')),
                    ],
                  ),
                  const Divider(height: 24),
                  Text('Usage today (UTC)', style: theme.textTheme.labelLarge),
                  const SizedBox(height: 6),
                  Text(
                    'Inbound (customer): ${_int(usage['inbound_customer_messages'])} · '
                    'AI out: ${_int(usage['outbound_ai_messages'])} · '
                    'Agent out: ${_int(usage['outbound_agent_messages'])}',
                    style: theme.textTheme.bodySmall,
                  ),
                  if (usage['soft_threshold_crossed_at'] != null ||
                      usage['hard_threshold_crossed_at'] != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                        'Thresholds: soft=${usage['soft_threshold_crossed_at'] ?? '—'} · '
                        'hard=${usage['hard_threshold_crossed_at'] ?? '—'}',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.error,
                        ),
                      ),
                    ),
                  const Divider(height: 24),
                  Text('Messages last 7 days', style: theme.textTheme.labelLarge),
                  const SizedBox(height: 6),
                  Text(
                    'Customer ${_int(msg7['customer'])} · AI ${_int(msg7['ai'])} · '
                    'Agent ${_int(msg7['agent'])} · System ${_int(msg7['system'])}',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text('Agents', style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          Card(
            child: agentList.isEmpty
                ? const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No agents in this client.'),
                  )
                : ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: agentList.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, i) {
                      final r = agentList[i];
                      return ListTile(
                        title: Text(_str(r['email']) ?? _str(r['name']) ?? _str(r['user_id']) ?? '—'),
                        subtitle: Text(_str(r['name']) ?? ''),
                        trailing: Text(
                          '${_int(r['replies_last_7d'])} replies · ${_int(r['active_assigned_chats'])} active',
                          style: theme.textTheme.labelSmall,
                        ),
                      );
                    },
                  ),
          ),
          const SizedBox(height: 24),
          Text('Quality', style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Pending agent (queue): ${_int(qu['chats_pending_agent'])}'),
                  const SizedBox(height: 6),
                  Text('Chats with handoff reason (7d): ${_int(qu['chats_with_handoff_reason_7d'])}'),
                  if (qu['median_first_response_seconds'] != null)
                    Text('Median first response (s): ${qu['median_first_response_seconds']}'),
                  const Divider(height: 20),
                  Text('Messages last 7 days', style: theme.textTheme.labelLarge),
                  const SizedBox(height: 6),
                  Text(
                    'Customer ${_int(quMsg7['customer'])} · AI ${_int(quMsg7['ai'])} · '
                    'Agent ${_int(quMsg7['agent'])} · System ${_int(quMsg7['system'])}',
                    style: theme.textTheme.bodySmall,
                  ),
                  if (_str(qu['notes']) != null) ...[
                    const SizedBox(height: 8),
                    Text(_str(qu['notes'])!, style: theme.textTheme.labelSmall),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}
