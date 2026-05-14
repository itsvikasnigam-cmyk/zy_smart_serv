import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';

Future<void> showSuperAdminApiSettingsSheet(BuildContext context) async {
  final session = context.read<SessionController>();
  final clientCtrl = TextEditingController(text: session.config.apiBaseUrl);
  final opsCtrl = TextEditingController(text: session.opsConfig.apiBaseUrl);

  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (ctx) {
      return Padding(
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 8,
          bottom: 20 + MediaQuery.viewInsetsOf(ctx).bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('API bases', style: Theme.of(ctx).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              'client_api: login + inbox. ops_api: SOPs & runs (same JWT). '
              'Android emulator host: http://10.0.2.2:8085 / :8087',
              style: Theme.of(ctx).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: clientCtrl,
              decoration: const InputDecoration(
                labelText: 'CLIENT_API_BASE_URL',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: opsCtrl,
              decoration: const InputDecoration(
                labelText: 'OPS_API_BASE_URL',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () {
                session.setBaseUrl(clientCtrl.text.trim());
                session.setOpsBaseUrl(opsCtrl.text.trim());
                Navigator.pop(ctx);
              },
              child: const Text('Save'),
            ),
            const SizedBox(height: 8),
            Text(
              'Build-time: flutter run '
              '--dart-define=CLIENT_API_BASE_URL=... '
              '--dart-define=OPS_API_BASE_URL=...',
              style: Theme.of(ctx).textTheme.bodySmall,
            ),
          ],
        ),
      );
    },
  );

  clientCtrl.dispose();
  opsCtrl.dispose();
}
