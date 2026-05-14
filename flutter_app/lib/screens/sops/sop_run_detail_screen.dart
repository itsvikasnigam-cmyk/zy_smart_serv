import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/sop_models.dart';
import '../../state/session_controller.dart';
import '../../utils/ops_api_auth.dart';

class SopRunDetailScreen extends StatefulWidget {
  const SopRunDetailScreen({super.key, required this.runId});

  final String runId;

  @override
  State<SopRunDetailScreen> createState() => _SopRunDetailScreenState();
}

class _SopRunDetailScreenState extends State<SopRunDetailScreen> {
  RunLog? _run;
  Object? _error;
  bool _loading = true;

  Future<void> _load() async {
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await session.opsApi.getRun(token: token, runId: widget.runId);
      setState(() {
        _run = r;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      if (handleOpsUnauthorizedAndForbidden(
        context,
        e,
        onMessage: (m) => setState(() => _error = m),
      )) {
        setState(() => _loading = false);
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
    final df = DateFormat.yMMMd().add_Hm();
    final pretty = _run == null
        ? ''
        : const JsonEncoder.withIndent('  ').convert(_run!.contextJson);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Run detail'),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('$_error'))
              : _run == null
                  ? const Center(child: Text('Not found'))
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        SelectableText('Run id: ${_run!.id}'),
                        SelectableText('SOP id: ${_run!.sopId}'),
                        Text('Version at run: ${_run!.sopVersionAtRun}'),
                        Text('Trigger: ${_run!.triggerType}'),
                        Text('Created: ${df.format(_run!.createdAt.toLocal())}'),
                        if (_run!.clientId != null) SelectableText('client_id: ${_run!.clientId}'),
                        if (_run!.createdByUserId != null)
                          SelectableText('created_by: ${_run!.createdByUserId}'),
                        const SizedBox(height: 16),
                        Text('context_json', style: theme.textTheme.titleMedium),
                        const SizedBox(height: 8),
                        SelectableText(
                          pretty,
                          style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
                        ),
                      ],
                    ),
    );
  }
}
