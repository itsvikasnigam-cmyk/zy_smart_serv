import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';

class ConnectionSettingsScreen extends StatefulWidget {
  const ConnectionSettingsScreen({super.key});

  @override
  State<ConnectionSettingsScreen> createState() =>
      _ConnectionSettingsScreenState();
}

class _ConnectionSettingsScreenState extends State<ConnectionSettingsScreen> {
  final _url = TextEditingController();
  bool _seeded = false;

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_seeded) {
      _seeded = true;
      final s = context.read<SessionController>();
      _url.text = s.config.apiBaseUrl;
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return Scaffold(
      appBar: AppBar(title: const Text('API base URL')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Default: http://127.0.0.1:8085 (client_api). '
              'Android emulator reaches the host at http://10.0.2.2:8085.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _url,
              decoration: const InputDecoration(
                labelText: 'Base URL',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () async {
                session.setBaseUrl(_url.text.trim());
                await session.disconnectWebSocket();
                if (session.isLoggedIn && session.usesTenantInbox) {
                  await session.connectWebSocket();
                }
                if (context.mounted) Navigator.pop(context);
              },
              child: const Text('Save'),
            ),
            const SizedBox(height: 8),
            Text(
              'Build-time override: flutter run '
              '--dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
