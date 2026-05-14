import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';
import 'connection_settings_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final session = context.read<SessionController>();
    try {
      await session.login(_email.text.trim(), _password.text);
      if (!mounted) return;
      final u = session.user;
      if (u == null) return;
      if (u.isSuperAdmin) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Signed in as super_admin — use the link icon for API bases (client_api + ops_api); SOPs, Runs, Control, Dash.',
            ),
          ),
        );
        return;
      }
      if (u.isOwner) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Signed in as owner — Inbox (assign agents), Dashboard (tenant metrics), Settings.',
            ),
          ),
        );
      } else if (u.isAgent) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Signed in as agent — Inbox (your queue), Dashboard, Settings. Replies only on assigned chats.',
            ),
          ),
        );
      }
      await session.connectWebSocket();
      if (!mounted) return;
      if (!session.wsConnected && session.wsLastError != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Inbox works over REST; live updates failed: ${session.wsLastError}',
            ),
          ),
        );
      }
      _password.clear();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(session.lastError ?? 'Login failed')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    return Scaffold(
      appBar: AppBar(title: const Text('ZY Smart Serv')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Sign in',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Endpoint: ${session.config.apiBaseUrl}/auth/login',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Owner or agent: inbox, WebSocket, and read-only client dashboard '
                    '(`GET /dash/client/*`). Super admin uses Settings + SOP tools.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 24),
                  TextFormField(
                    controller: _email,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _password,
                    decoration: const InputDecoration(
                      labelText: 'Password',
                      border: OutlineInputBorder(),
                    ),
                    obscureText: true,
                    validator: (v) =>
                        (v == null || v.isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: session.busy ? null : _submit,
                    child: session.busy
                        ? const SizedBox(
                            height: 22,
                            width: 22,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Continue'),
                  ),
                  TextButton(
                    onPressed: () {
                      Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => const ConnectionSettingsScreen(),
                        ),
                      );
                    },
                    child: const Text('Connection settings'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
