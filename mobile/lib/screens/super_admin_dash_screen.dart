import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/client_api_repository.dart';
import '../state/session_controller.dart';

/// Read-only **Chat J** admin aggregates (`GET /dash/admin/*`) on `client_api`.
class SuperAdminDashScreen extends StatefulWidget {
  const SuperAdminDashScreen({super.key});

  @override
  State<SuperAdminDashScreen> createState() => _SuperAdminDashScreenState();
}

class _DashEndpoint {
  _DashEndpoint({required this.title, required this.path});
  final String title;
  final String path;
  Map<String, dynamic>? data;
  String? error;
  bool loading = false;
}

class _SuperAdminDashScreenState extends State<SuperAdminDashScreen> {
  late final List<_DashEndpoint> _endpoints;

  @override
  void initState() {
    super.initState();
    _endpoints = [
      _DashEndpoint(title: 'Admin overview', path: '/dash/admin/overview'),
      _DashEndpoint(title: 'Collections', path: '/dash/admin/collections'),
      _DashEndpoint(title: 'Razorpay provider', path: '/dash/admin/providers/razorpay'),
      _DashEndpoint(title: 'Paddle provider', path: '/dash/admin/providers/paddle'),
      _DashEndpoint(title: 'WhatsApp ops', path: '/dash/admin/ops/whatsapp'),
      _DashEndpoint(title: 'Geo', path: '/dash/admin/geo'),
    ];
  }

  Future<void> _load(int i) async {
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _endpoints[i].loading = true;
      _endpoints[i].error = null;
    });
    try {
      final m = await session.api.dashGet(token, _endpoints[i].path);
      if (!mounted) return;
      setState(() {
        _endpoints[i].data = m;
        _endpoints[i].loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      if (e is ApiUnauthorizedException) {
        session.logout();
        return;
      }
      setState(() {
        _endpoints[i].error = e.toString();
        _endpoints[i].loading = false;
      });
    }
  }

  Future<void> _loadAll() async {
    for (var i = 0; i < _endpoints.length; i++) {
      await _load(i);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin dashboards'),
        actions: [
          IconButton(
            tooltip: 'Load all',
            onPressed: _loadAll,
            icon: const Icon(Icons.cloud_download_outlined),
          ),
        ],
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _endpoints.length + 1,
        itemBuilder: (context, i) {
          if (i == 0) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(
                'Read-only aggregates from client_api. Empty or zero sections are normal until workers and billing data exist.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            );
          }
          final ep = _endpoints[i - 1];
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: ExpansionTile(
              title: Text(ep.title),
              subtitle: Text(ep.path, style: theme.textTheme.bodySmall),
              children: [
                if (ep.loading)
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (ep.error != null)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(ep.error!, style: TextStyle(color: theme.colorScheme.error)),
                  )
                else if (ep.data == null)
                  Padding(
                    padding: const EdgeInsets.all(8),
                    child: FilledButton.tonal(
                      onPressed: () => _load(i - 1),
                      child: const Text('Load'),
                    ),
                  )
                else
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: SelectableText(
                      const JsonEncoder.withIndent('  ').convert(ep.data),
                      style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}
