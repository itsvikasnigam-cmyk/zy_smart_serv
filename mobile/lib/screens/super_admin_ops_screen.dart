import 'package:flutter/material.dart';

class SuperAdminOpsScreen extends StatelessWidget {
  const SuperAdminOpsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          'Control plane',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(
          'Placeholder for super-admin operations. The backend will expose '
          'read/write APIs for ops_runtime_config (key/value, typed JSON).',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: 24),
        Text(
          'Keys already used by the AI engine contract (documented in HANDOFF):',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        _Bullet('ai.urgent_bypass_substrings — JSON array of substrings that force an urgent REPLY path'),
        _Bullet('ai.needs_owner_data_customer_reply — optional string override for the fixed NEEDS_OWNER_DATA customer line'),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              'Next step: add authenticated admin routes in client_api (or a '
              'dedicated ops service), then wire this screen to list/update keys.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        ),
      ],
    );
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('• '),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
