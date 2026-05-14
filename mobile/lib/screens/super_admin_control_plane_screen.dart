import 'package:flutter/material.dart';

/// Read-only **M8 interactive control plane** placeholders + legacy notes.
///
/// There is **no** safe write API for `ops_runtime_config` in this repo yet — do not POST from the client.
class SuperAdminControlPlaneScreen extends StatelessWidget {
  const SuperAdminControlPlaneScreen({super.key});

  Widget _panel(
    BuildContext context, {
    required String title,
    required String keysHint,
  }) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(keysHint, style: theme.textTheme.bodySmall),
            const SizedBox(height: 8),
            Text(
              'Read-only — Stem: needs authenticated read/write APIs (or admin-only routes) before editing from Flutter.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Control plane (read-only)', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(
          'Per checklist § M8 interactive panels: show safe placeholders until backend APIs exist.',
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 20),
        _panel(
          context,
          title: 'Runtime config (`ops_runtime_config`)',
          keysHint: 'Examples: debounce.seconds, debounce.max_seconds, ai.urgent_bypass_substrings, '
              'ai.needs_owner_data_customer_reply, usage.daily_inbound_limits, ai.fallback.*',
        ),
        _panel(
          context,
          title: 'Pricing (India)',
          keysHint: 'Blueprint: pricing.in.* (minor units). No REST contract in repo yet.',
        ),
        _panel(
          context,
          title: 'Debounce & adaptive batching',
          keysHint: 'debounce.*, debounce.adaptive.* — tuned via DB rows today; UI editor pending Stem.',
        ),
        _panel(
          context,
          title: 'Urgent bypass',
          keysHint: 'routing.urgent_* / ai.urgent_bypass_substrings — see HANDOFF for AI engine keys.',
        ),
        _panel(
          context,
          title: 'AI fallback & rate limits',
          keysHint: 'ai.fallback.*, max_rate_per_client — no write API from Flutter.',
        ),
        const SizedBox(height: 24),
        Text('Notes', style: theme.textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          'Tenant-scoped inbox WebSocket for super_admin still requires a client_id scope on client_api; '
          'SOP Runbook uses ops_api with the same JWT and does not need that scope.',
          style: theme.textTheme.bodySmall,
        ),
      ],
    );
  }
}
