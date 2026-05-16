import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../services/billing_api_repository.dart';
import '../services/client_api_repository.dart';
import '../state/session_controller.dart';

/// Owner/agent billing summary (`billing_api` on port 8086).
class OwnerBillingScreen extends StatefulWidget {
  const OwnerBillingScreen({super.key});

  @override
  State<OwnerBillingScreen> createState() => _OwnerBillingScreenState();
}

class _OwnerBillingScreenState extends State<OwnerBillingScreen> {
  Map<String, dynamic>? _sub;
  List<Map<String, dynamic>>? _invoices;
  String? _error;
  bool _loading = false;

  String _money(int? minor, String currency) {
    if (minor == null) return '—';
    final sym = currency == 'INR' ? '₹' : '$currency ';
    return '$sym${(minor / 100).toStringAsFixed(2)}';
  }

  Future<void> _load() async {
    final session = context.read<SessionController>();
    final token = session.token;
    final user = session.user;
    if (token == null || user == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final sub = await session.billingApi.getSubscription(
        token: token,
        user: user,
      );
      final inv = await session.billingApi.getInvoices(
        token: token,
        user: user,
        limit: 30,
      );
      if (!mounted) return;
      setState(() {
        _sub = sub;
        _invoices = inv;
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

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final session = context.watch<SessionController>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Billing'),
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
            'Subscription and invoices from billing_api (${session.billingConfig.apiBaseUrl}).',
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'On Windows use the Refresh button. Start billing_api on port 8086.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          if (_loading) const Center(child: CircularProgressIndicator()),
          if (_error != null)
            Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
          if (_sub != null) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Plan', style: theme.textTheme.titleMedium),
                    const SizedBox(height: 8),
                    _row('Entitlement', '${_sub!['entitlement_plan']}'),
                    _row('Plan code', '${_sub!['billing_plan_code'] ?? '—'}'),
                    _row('Provider', '${_sub!['billing_provider'] ?? '—'}'),
                    _row('Trial ends', '${_sub!['trial_end'] ?? '—'}'),
                    if (_sub!['subscription'] is Map) ...[
                      const Divider(),
                      Text('Latest subscription row', style: theme.textTheme.labelLarge),
                      _row('Status', '${(_sub!['subscription'] as Map)['status']}'),
                      _row(
                        'Period end',
                        '${(_sub!['subscription'] as Map)['current_period_end'] ?? '—'}',
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 12),
          Text('Invoices (${_invoices?.length ?? 0})', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_invoices != null && _invoices!.isEmpty)
            const Text('No invoices in the database yet.'),
          if (_invoices != null)
            ..._invoices!.map((inv) {
              final issued = inv['issued_at'] as String?;
              final dt = issued != null ? DateTime.tryParse(issued) : null;
              return Card(
                child: ListTile(
                  title: Text(
                    _money(inv['amount_minor'] as int?, '${inv['currency'] ?? 'INR'}'),
                  ),
                  subtitle: Text(
                    '${inv['provider']} · ${inv['status']}\n'
                    '${dt != null ? DateFormat.yMMMd().add_jm().format(dt.toLocal()) : issued ?? '—'}',
                  ),
                  isThreeLine: true,
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 120, child: Text(label)),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }
}
