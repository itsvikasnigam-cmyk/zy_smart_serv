import 'package:flutter/material.dart';

/// Placeholder until a real super-admin API exists.
/// Server-side `ops_runtime_config` is read by the AI engine today; this UI is static.
class SuperAdminControlPlaneScreen extends StatelessWidget {
  const SuperAdminControlPlaneScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('Super admin', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 12),
        Text(
          'This screen is a stub for the future control plane (tenant management, '
          'billing, feature flags, and ops_runtime_config editing).',
          style: theme.textTheme.bodyLarge,
        ),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ops_runtime_config (examples)', style: theme.textTheme.titleMedium),
                const SizedBox(height: 8),
                SelectableText(
                  'ai.urgent_bypass_substrings — JSON array of substrings that force urgent REPLY.\n'
                  'ai.needs_owner_data_customer_reply — optional override for NEEDS_OWNER_DATA line.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontFamily: 'monospace',
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'Tenant-scoped REST and WebSocket for super_admin require a client_id query '
          'parameter on the server; this placeholder does not call those APIs yet.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}
