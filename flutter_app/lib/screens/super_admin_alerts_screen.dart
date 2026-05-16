import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/alert_models.dart';
import '../state/session_controller.dart';
import '../utils/ops_api_auth.dart';

/// M7: read ``ops_alert_events`` via ``GET /ops/alerts``.
class SuperAdminAlertsScreen extends StatefulWidget {
  const SuperAdminAlertsScreen({super.key});

  @override
  State<SuperAdminAlertsScreen> createState() => _SuperAdminAlertsScreenState();
}

class _SuperAdminAlertsScreenState extends State<SuperAdminAlertsScreen> {
  final _typeFilter = TextEditingController();
  final List<OpsAlertEvent> _items = [];
  String? _cursor;
  String? _error;
  bool _loading = false;

  @override
  void dispose() {
    _typeFilter.dispose();
    super.dispose();
  }

  Future<void> _load({bool more = false}) async {
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await session.opsApi.listAlerts(
        token: token,
        cursor: more ? _cursor : null,
        alertType: _typeFilter.text.trim().isEmpty ? null : _typeFilter.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        if (!more) _items.clear();
        _items.addAll(page.items);
        _cursor = page.nextCursor;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      if (handleOpsUnauthorizedAndForbidden(
        context,
        e,
        onMessage: (m) => setState(() => _error = m),
      )) {
        setState(() => _loading = false);
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Color _severityColor(BuildContext context, String severity) {
    final scheme = Theme.of(context).colorScheme;
    switch (severity) {
      case 'error':
        return scheme.error;
      case 'warning':
        return scheme.tertiary;
      default:
        return scheme.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Ops alerts (M7)', style: theme.textTheme.titleLarge),
              const SizedBox(height: 8),
              TextField(
                controller: _typeFilter,
                decoration: const InputDecoration(
                  labelText: 'alert_type filter (optional)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  FilledButton(
                    onPressed: _loading ? null : () => _load(),
                    child: const Text('Refresh'),
                  ),
                  const SizedBox(width: 8),
                  OutlinedButton(
                    onPressed: _loading || _cursor == null ? null : () => _load(more: true),
                    child: const Text('Load more'),
                  ),
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
            ],
          ),
        ),
        Expanded(
          child: _items.isEmpty && !_loading
              ? Center(
                  child: Text(
                    'No alerts loaded. Tap Refresh.',
                    style: theme.textTheme.bodyMedium,
                  ),
                )
              : ListView.builder(
                  itemCount: _items.length,
                  itemBuilder: (context, i) {
                    final a = _items[i];
                    return ListTile(
                      leading: Icon(
                        Icons.notifications_active_outlined,
                        color: _severityColor(context, a.severity),
                      ),
                      title: Text(a.summary),
                      subtitle: Text(
                        '${a.alertType} · ${a.severity}\n${a.createdAt}',
                      ),
                      isThreeLine: true,
                      onTap: () {
                        showDialog<void>(
                          context: context,
                          builder: (ctx) => AlertDialog(
                            title: Text(a.alertType),
                            content: SingleChildScrollView(
                              child: SelectableText(
                                '${a.summary}\n\n${a.detailJson}',
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
                    );
                  },
                ),
        ),
      ],
    );
  }
}
