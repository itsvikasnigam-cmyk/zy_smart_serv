import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';
import 'connection_settings_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _clientId = TextEditingController();
  bool _seeded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_seeded) {
      _seeded = true;
      _clientId.text = context.read<SessionController>().superAdminClientId ?? '';
    }
  }

  @override
  void dispose() {
    _clientId.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final user = session.user!;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        ListTile(
          title: Text(user.name ?? user.email ?? user.id),
          subtitle: Text('${user.role} · ${user.clientId ?? 'no client in token'}'),
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
        if (user.isSuperAdmin) ...[
          const SizedBox(height: 8),
          TextField(
            controller: _clientId,
            decoration: const InputDecoration(
              labelText: 'Tenant client_id (UUID)',
              helperText: 'Required for super_admin REST + WebSocket',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: () async {
              session.setSuperAdminClientId(_clientId.text.trim());
              session.bumpInboxGeneration();
              await session.disconnectWebSocket();
              await session.connectWebSocket();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Saved client scope')),
                );
              }
            },
            child: const Text('Save client scope'),
          ),
        ],
        const Divider(),
        SwitchListTile(
          title: const Text('WebSocket connected'),
          subtitle: Text(
            session.wsConnected
                ? 'Receiving hello / message_new / …'
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
          title: const Text('Ping over WebSocket'),
          trailing: const Icon(Icons.sensors),
          onTap: session.wsConnected ? () => session.ws.sendPing() : null,
        ),
        ExpansionTile(
          title: const Text('Recent WebSocket lines'),
          children: [
            for (final line in session.wsRecentLines)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                child: SelectableText(line, style: Theme.of(context).textTheme.bodySmall),
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
          onPressed: () {
            session.logout();
          },
          child: const Text('Log out'),
        ),
      ],
    );
  }
}
