import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/sop_models.dart';
import '../../state/session_controller.dart';
import '../../utils/ops_api_auth.dart';
import '../../widgets/safe_markdown_body.dart';
import 'sop_editor_screen.dart';
import 'sop_run_start_screen.dart';
import 'sop_versions_screen.dart';

class SopDetailScreen extends StatefulWidget {
  const SopDetailScreen({super.key, required this.sopId});

  final String sopId;

  @override
  State<SopDetailScreen> createState() => _SopDetailScreenState();
}

class _SopDetailScreenState extends State<SopDetailScreen> {
  SopDetail? _detail;
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
      final d = await session.opsApi.getSop(token: token, sopId: widget.sopId);
      setState(() {
        _detail = d;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      if (handleOpsUnauthorizedAndForbidden(
        context,
        e,
        onMessage: (m) => setState(() => _error = m),
      )) {
        setState(() {
          _loading = false;
        });
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
    return Scaffold(
      appBar: AppBar(
        title: Text(_detail?.title ?? 'SOP'),
        actions: [
          if (_detail != null) ...[
            IconButton(
              tooltip: 'Version history',
              onPressed: () async {
                final changed = await Navigator.of(context).push<bool>(
                  MaterialPageRoute(
                    builder: (_) => SopVersionsScreen(
                      sopId: widget.sopId,
                      title: _detail!.title,
                    ),
                  ),
                );
                if (changed == true && mounted) {
                  await _load();
                }
              },
              icon: const Icon(Icons.history),
            ),
            IconButton(
              tooltip: 'Start run',
              onPressed: () async {
                await Navigator.of(context).push<void>(
                  MaterialPageRoute(
                    builder: (_) => SopRunStartScreen(
                      sopId: widget.sopId,
                      sopTitle: _detail!.title,
                    ),
                  ),
                );
              },
              icon: const Icon(Icons.play_arrow),
            ),
            IconButton(
              tooltip: 'Edit',
              onPressed: () async {
                final ok = await Navigator.of(context).push<bool>(
                  MaterialPageRoute(
                    builder: (_) => SopEditorScreen.edit(sopId: widget.sopId),
                  ),
                );
                if (ok == true && mounted) {
                  await _load();
                }
              },
              icon: const Icon(Icons.edit),
            ),
          ],
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('$_error', textAlign: TextAlign.center))
              : _detail == null
                  ? const Center(child: Text('Not found'))
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        Text(
                          'Slug: ${_detail!.slug} · v${_detail!.currentVersion} · ${_detail!.status}',
                          style: theme.textTheme.titleSmall,
                        ),
                        if (_detail!.category != null)
                          Text('Category: ${_detail!.category}'),
                        Text(
                          'Updated ${df.format(_detail!.updatedAt.toLocal())}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text('Preview', style: theme.textTheme.titleMedium),
                        const SizedBox(height: 8),
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: SafeMarkdownBody(
                              data: _detail!.bodyMarkdown,
                            ),
                          ),
                        ),
                      ],
                    ),
    );
  }
}
