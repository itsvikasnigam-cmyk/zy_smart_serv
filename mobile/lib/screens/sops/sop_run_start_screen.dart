import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../state/session_controller.dart';
import '../../utils/ops_api_auth.dart';
import 'sop_run_detail_screen.dart';

class SopRunStartScreen extends StatefulWidget {
  const SopRunStartScreen({
    super.key,
    required this.sopId,
    required this.sopTitle,
  });

  final String sopId;
  final String sopTitle;

  @override
  State<SopRunStartScreen> createState() => _SopRunStartScreenState();
}

class _KvRow {
  _KvRow() : key = TextEditingController(), value = TextEditingController();
  final TextEditingController key;
  final TextEditingController value;
  void dispose() {
    key.dispose();
    value.dispose();
  }
}

class _SopRunStartScreenState extends State<SopRunStartScreen> {
  final _clientId = TextEditingController();
  final _rawJson = TextEditingController(text: '{\n  "notes": ""\n}');
  final List<_KvRow> _kvRows = [_KvRow()];
  String _trigger = 'manual';
  bool _rawMode = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _clientId.dispose();
    _rawJson.dispose();
    for (final r in _kvRows) {
      r.dispose();
    }
    super.dispose();
  }

  Map<String, dynamic> _contextFromKv() {
    final m = <String, dynamic>{};
    for (final r in _kvRows) {
      final k = r.key.text.trim();
      if (k.isEmpty) continue;
      m[k] = r.value.text;
    }
    return m;
  }

  void _syncRawFromKv() {
    _rawJson.text = const JsonEncoder.withIndent('  ').convert(_contextFromKv());
  }

  void _syncKvFromRaw() {
    try {
      final decoded = jsonDecode(_rawJson.text);
      if (decoded is! Map) {
        setState(() => _error = 'context_json must be a JSON object');
        return;
      }
      for (final r in _kvRows) {
        r.dispose();
      }
      _kvRows.clear();
      for (final e in (decoded as Map<dynamic, dynamic>).entries) {
        final row = _KvRow();
        row.key.text = e.key.toString();
        final v = e.value;
        row.value.text = v is String ? v : jsonEncode(v);
        _kvRows.add(row);
      }
      if (_kvRows.isEmpty) {
        _kvRows.add(_KvRow());
      }
      setState(() => _error = null);
    } catch (e) {
      setState(() => _error = 'Invalid JSON: $e');
    }
  }

  Future<void> _submit() async {
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;

    Map<String, dynamic> ctx;
    if (_rawMode) {
      try {
        final decoded = jsonDecode(_rawJson.text);
        if (decoded is! Map<String, dynamic>) {
          setState(() => _error = 'context_json must be a JSON object');
          return;
        }
        ctx = Map<String, dynamic>.from(decoded);
      } catch (e) {
        setState(() => _error = 'Invalid JSON: $e');
        return;
      }
    } else {
      ctx = _contextFromKv();
    }

    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final res = await session.opsApi.startRun(
        token: token,
        sopId: widget.sopId,
        contextJson: ctx,
        triggerType: _trigger,
        clientId: _clientId.text.trim().isEmpty ? null : _clientId.text.trim(),
      );
      if (!mounted) return;
      setState(() => _busy = false);
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Run started'),
          content: SelectableText(
            'Run id: ${res.id}\nSOP version at run: ${res.sopVersionAtRun}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Close'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(
                    builder: (_) => SopRunDetailScreen(runId: res.id),
                  ),
                );
              },
              child: const Text('Open run'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (!mounted) return;
      if (handleOpsUnauthorizedAndForbidden(
        context,
        e,
        onMessage: (m) => setState(() => _error = m),
      )) {
        setState(() => _busy = false);
        return;
      }
      setState(() {
        _busy = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text('Start run · ${widget.sopTitle}'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'POST /ops/sops/{id}/run — context_json is stored for auditing.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            ),
          DropdownButtonFormField<String>(
            value: _trigger,
            decoration: const InputDecoration(
              labelText: 'Trigger type',
              border: OutlineInputBorder(),
            ),
            items: const [
              DropdownMenuItem(value: 'manual', child: Text('manual')),
              DropdownMenuItem(value: 'auto', child: Text('auto')),
              DropdownMenuItem(value: 'scheduled', child: Text('scheduled')),
              DropdownMenuItem(value: 'other', child: Text('other')),
            ],
            onChanged: (v) {
              if (v != null) setState(() => _trigger = v);
            },
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _clientId,
            decoration: const InputDecoration(
              labelText: 'client_id (optional UUID)',
              border: OutlineInputBorder(),
              helperText: 'Must exist in api_clients when set',
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Text('Context', style: theme.textTheme.titleSmall),
              const Spacer(),
              FilterChip(
                label: const Text('Key / value'),
                selected: !_rawMode,
                onSelected: (sel) {
                  if (!sel) return;
                  if (_rawMode) {
                    _syncKvFromRaw();
                    if (_error != null) return;
                  }
                  setState(() => _rawMode = false);
                },
              ),
              const SizedBox(width: 8),
              FilterChip(
                label: const Text('Raw JSON'),
                selected: _rawMode,
                onSelected: (sel) {
                  if (!sel) return;
                  if (!_rawMode) {
                    _syncRawFromKv();
                  }
                  setState(() => _rawMode = true);
                },
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (_rawMode) ...[
            TextField(
              controller: _rawJson,
              decoration: const InputDecoration(
                labelText: 'context_json',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              minLines: 12,
              maxLines: 28,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
            ),
          ] else ...[
            ..._kvRows.asMap().entries.map((entry) {
              final i = entry.key;
              final r = entry.value;
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 2,
                      child: TextField(
                        controller: r.key,
                        decoration: const InputDecoration(
                          labelText: 'Key',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      flex: 3,
                      child: TextField(
                        controller: r.value,
                        decoration: const InputDecoration(
                          labelText: 'Value',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Remove row',
                      onPressed: _kvRows.length <= 1
                          ? null
                          : () {
                              setState(() {
                                _kvRows[i].dispose();
                                _kvRows.removeAt(i);
                              });
                            },
                      icon: const Icon(Icons.remove_circle_outline),
                    ),
                  ],
                ),
              );
            }),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => setState(() => _kvRows.add(_KvRow())),
                icon: const Icon(Icons.add),
                label: const Text('Add field'),
              ),
            ),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy ? null : _submit,
            child: _busy
                ? const SizedBox(
                    height: 22,
                    width: 22,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Start run'),
          ),
        ],
      ),
    );
  }
}
