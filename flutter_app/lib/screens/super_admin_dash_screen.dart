import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/client_api_repository.dart';
import '../state/session_controller.dart';
import '../widgets/dash_bar_charts.dart';

/// Read-only **Chat J** admin aggregates (`GET /dash/admin/*`) on `client_api`
/// with **phase-1 charts** (dict counts + message rollup bar) where JSON shape matches backend models.
class SuperAdminDashScreen extends StatefulWidget {
  const SuperAdminDashScreen({super.key});

  @override
  State<SuperAdminDashScreen> createState() => _SuperAdminDashScreenState();
}

class _DashEndpoint {
  _DashEndpoint({required this.title, required this.path});
  final String title;
  final String path;
  Map<String, dynamic>? data;
  String? error;
  bool loading = false;
}

class _SuperAdminDashScreenState extends State<SuperAdminDashScreen> {
  late final List<_DashEndpoint> _endpoints;

  bool _autoLoadDone = false;

  @override
  void initState() {
    super.initState();
    _endpoints = [
      _DashEndpoint(title: 'Admin overview', path: '/dash/admin/overview'),
      _DashEndpoint(title: 'Collections', path: '/dash/admin/collections'),
      _DashEndpoint(title: 'Razorpay provider', path: '/dash/admin/providers/razorpay'),
      _DashEndpoint(title: 'Paddle provider', path: '/dash/admin/providers/paddle'),
      _DashEndpoint(title: 'WhatsApp ops', path: '/dash/admin/ops/whatsapp'),
      _DashEndpoint(title: 'Geo', path: '/dash/admin/geo'),
    ];
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_autoLoadDone && mounted) {
        _autoLoadDone = true;
        _loadAll();
      }
    });
  }

  Future<void> _load(int i) async {
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _endpoints[i].loading = true;
      _endpoints[i].error = null;
    });
    try {
      final m = await session.api.dashGet(token, _endpoints[i].path);
      if (!mounted) return;
      setState(() {
        _endpoints[i].data = m;
        _endpoints[i].loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      if (e is ApiUnauthorizedException) {
        session.logout();
        return;
      }
      setState(() {
        _endpoints[i].error = e.toString();
        _endpoints[i].loading = false;
      });
    }
  }

  Future<void> _loadAll() async {
    for (var i = 0; i < _endpoints.length; i++) {
      await _load(i);
    }
  }

  Widget _chartBodyForPath(String path, Map<String, dynamic> d) {
    switch (path) {
      case '/dash/admin/overview':
        return _OverviewCharts(data: d);
      case '/dash/admin/collections':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (d['notes'] != null && d['notes'].toString().trim().isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  d['notes'].toString(),
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            DashKpiRow(
              items: [
                (label: 'Active subscriptions', value: dashAsInt(d['active_subscriptions'])),
                (label: 'MRR stub (minor units)', value: dashAsInt(d['estimated_mrr_minor_units'])),
              ],
            ),
            const SizedBox(height: 12),
            DashDictBarCard(title: 'By provider', data: dashIntMapFromJson(d['by_provider'])),
            DashDictBarCard(title: 'By status', data: dashIntMapFromJson(d['by_status'])),
          ],
        );
      case '/dash/admin/providers/razorpay':
      case '/dash/admin/providers/paddle':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            DashKpiRow(
              items: [
                (label: 'Events (7d)', value: dashAsInt(d['events_last_7d'])),
                (label: 'Plans configured', value: dashAsInt(d['plans_configured'])),
              ],
            ),
            const SizedBox(height: 12),
            DashDictBarCard(
              title: 'Subscriptions by status',
              data: dashIntMapFromJson(d['subscriptions_by_status']),
            ),
          ],
        );
      case '/dash/admin/ops/whatsapp':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            DashDictBarCard(title: 'WA numbers by type', data: dashIntMapFromJson(d['wa_numbers_by_type'])),
            DashDictBarCard(title: 'Outbox by status', data: dashIntMapFromJson(d['outbox_by_status'])),
            DashDictBarCard(title: 'Outbox by kind', data: dashIntMapFromJson(d['outbox_by_kind'])),
          ],
        );
      case '/dash/admin/geo':
        final rows = d['rows'];
        final geo = <String, int>{};
        if (rows is List) {
          for (final r in rows) {
            if (r is Map) {
              final cc = r['country_code']?.toString() ?? '?';
              geo[cc] = dashAsInt(r['wa_numbers']);
            }
          }
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (d['notes'] != null && d['notes'].toString().trim().isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  d['notes'].toString(),
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            DashDictBarCard(title: 'WA numbers by country', data: geo, maxRows: 24),
          ],
        );
      default:
        return const SizedBox.shrink();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final anyLoading = _endpoints.any((e) => e.loading);
    return ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _endpoints.length + 1,
        itemBuilder: (context, i) {
          if (i == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Admin dashboards',
                    style: theme.textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Live `GET /dash/admin/*` on client_api. Zeros are normal until '
                    'workers and billing data exist.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: anyLoading ? null : _loadAll,
                    icon: anyLoading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.cloud_download_outlined),
                    label: Text(anyLoading ? 'Loading…' : 'Load all dashboards'),
                  ),
                ],
              ),
            );
          }
          final ep = _endpoints[i - 1];
          final d = ep.data;
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: ExpansionTile(
              title: Text(ep.title),
              subtitle: Text(ep.path, style: theme.textTheme.bodySmall),
              children: [
                if (ep.loading)
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (ep.error != null)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(ep.error!, style: TextStyle(color: theme.colorScheme.error)),
                  )
                else if (d == null)
                  Padding(
                    padding: const EdgeInsets.all(8),
                    child: FilledButton.tonal(
                      onPressed: () => _load(i - 1),
                      child: const Text('Load'),
                    ),
                  )
                else
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _chartBodyForPath(ep.path, d),
                        const SizedBox(height: 8),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            onPressed: () {
                              showDialog<void>(
                                context: context,
                                builder: (ctx) => AlertDialog(
                                  title: const Text('Raw JSON'),
                                  content: SingleChildScrollView(
                                    child: SelectableText(
                                      const JsonEncoder.withIndent('  ').convert(d),
                                      style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
                                    ),
                                  ),
                                  actions: [
                                    TextButton(
                                      onPressed: () => Navigator.pop(ctx),
                                      child: const Text('Close'),
                                    ),
                                  ],
                                ),
                              );
                            },
                            icon: const Icon(Icons.code),
                            label: const Text('Raw JSON'),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          );
        },
    );
  }
}

class _OverviewCharts extends StatelessWidget {
  const _OverviewCharts({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final hourly = data['hourly_system_last_24h'];
    final dead48 = dashAsInt(data['hourly_outbox_dead_last_48h']);
    final created48 = dashAsInt(data['hourly_outbox_created_last_48h']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DashKpiRow(
          items: [
            (label: 'Clients', value: dashAsInt(data['total_clients'])),
            (label: 'Chats', value: dashAsInt(data['total_chats'])),
            (label: 'WA numbers', value: dashAsInt(data['total_wa_numbers'])),
            (label: 'Outbox created (48h)', value: created48),
            (label: 'Outbox → DEAD (48h)', value: dead48),
          ],
        ),
        const SizedBox(height: 12),
        DashMessageTotalsCard(
          title: 'Messages (rolled up, last 24h UTC)',
          raw: hourly,
        ),
        DashDictBarCard(
          title: 'Clients by entitlement',
          data: dashIntMapFromJson(data['clients_by_entitlement']),
        ),
        DashDictBarCard(
          title: 'Outbox by status (backlog / health)',
          data: dashIntMapFromJson(data['outbox_by_status']),
        ),
      ],
    );
  }
}
