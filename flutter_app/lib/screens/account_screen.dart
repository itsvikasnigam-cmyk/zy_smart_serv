import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';
import 'connection_settings_screen.dart';
import 'owner_billing_screen.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final user = session.user!;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        ListTile(
          title: Text(user.name ?? user.email ?? user.id),
          subtitle: Text('${user.role} · client ${user.clientId ?? '—'}'),
        ),
        const Divider(),
        ListTile(
          title: const Text('API base URL'),
          subtitle: Text(session.config.apiBaseUrl),
          trailing: const Icon(Icons.edit),
          onTap: () {
            Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => const ConnectionSettingsScreen(),
              ),
            );
          },
        ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.payments_outlined),
          title: const Text('Billing & subscription'),
          subtitle: const Text('Plan, trial, invoices (port 8086)'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {
            Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => const OwnerBillingScreen(),
              ),
            );
          },
        ),
        const Divider(),
        SwitchListTile(
          title: const Text('WebSocket'),
          subtitle: Text(
            session.wsLastError != null && !session.wsConnected
                ? 'Error: ${session.wsLastError}'
                : session.wsConnected
                    ? 'Connected to /ws (see recent events below)'
                    : 'Disconnected',
          ),
          value: session.wsConnected,
          onChanged: (v) async {
            if (v) {
              await session.connectWebSocket();
            } else {
              await session.disconnectWebSocket();
            }
          },
        ),
        ListTile(
          title: const Text('Ping WebSocket'),
          enabled: session.wsConnected,
          trailing: const Icon(Icons.sensors),
          onTap: session.wsConnected ? () => session.ws.sendPing() : null,
        ),
        ExpansionTile(
          title: const Text('Recent WebSocket events'),
          children: [
            for (final line in session.wsRecentLines)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                child: SelectableText(
                  line,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            if (session.wsRecentLines.isEmpty)
              const Padding(
                padding: EdgeInsets.all(12),
                child: Text('No events yet.'),
              ),
          ],
        ),
        const Divider(),
        FilledButton.tonal(
          onPressed: session.logout,
          child: const Text('Log out'),
        ),
      ],
    );
  }
}
