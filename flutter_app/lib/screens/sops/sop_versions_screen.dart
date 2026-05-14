import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/sop_models.dart';
import '../../state/session_controller.dart';
import '../../utils/line_diff.dart';
import '../../utils/ops_api_auth.dart';
import 'sop_editor_screen.dart';

class SopVersionsScreen extends StatefulWidget {
  const SopVersionsScreen({
    super.key,
    required this.sopId,
    required this.title,
  });

  final String sopId;
  final String title;

  @override
  State<SopVersionsScreen> createState() => _SopVersionsScreenState();
}

class _SopVersionsScreenState extends State<SopVersionsScreen> {
  List<SopVersion>? _versions;
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
      final list = await session.opsApi.listSopVersions(
        token: token,
        sopId: widget.sopId,
      );
      setState(() {
        _versions = list;
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

  Future<void> _openDiff(SopVersion a, SopVersion b) async {
    if (!mounted) return;
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => _SopVersionDiffPage(
          labelA: 'v${a.versionNum}',
          labelB: 'v${b.versionNum}',
          bodyA: a.bodyMarkdown,
          bodyB: b.bodyMarkdown,
        ),
      ),
    );
  }

  Future<void> _restore(SopVersion v) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Restore as new version?'),
        content: Text(
          'Opens the editor with Markdown from v${v.versionNum}. '
          'Saving runs PUT and appends a new immutable version.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Continue')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => SopEditorScreen.restore(
          sopId: widget.sopId,
          body: v.bodyMarkdown,
        ),
      ),
    );
    if (saved == true && mounted) {
      Navigator.of(context).pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final df = DateFormat.yMMMd().add_Hm();
    return Scaffold(
      appBar: AppBar(
        title: Text('History · ${widget.title}'),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('$_error'))
              : _versions == null || _versions!.isEmpty
                  ? const Center(child: Text('No versions'))
                  : ListView.separated(
                      itemCount: _versions!.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, i) {
                        final v = _versions![i];
                        final prev = i > 0 ? _versions![i - 1] : null;
                        final cur = _versions!.isNotEmpty ? _versions!.last : null;
                        return ListTile(
                          title: Text('Version ${v.versionNum}'),
                          subtitle: Text(df.format(v.createdAt.toLocal())),
                          trailing: PopupMenuButton<String>(
                            onSelected: (action) async {
                              if (action == 'preview') {
                                if (!mounted) return;
                                await showDialog<void>(
                                  context: context,
                                  builder: (ctx) => AlertDialog(
                                    title: Text('v${v.versionNum}'),
                                    content: SizedBox(
                                      width: double.maxFinite,
                                      child: SingleChildScrollView(
                                        child: SelectableText(
                                          v.bodyMarkdown,
                                          style: theme.textTheme.bodySmall?.copyWith(
                                            fontFamily: 'monospace',
                                          ),
                                        ),
                                      ),
                                    ),
                                    actions: [
                                      TextButton(
                                        onPressed: () => Navigator.pop(ctx),
                                        child: const Text('Close'),
                                      ),
                                    ],
                                  ),
                                );
                              } else if (action == 'diffPrev' && prev != null) {
                                await _openDiff(prev, v);
                              } else if (action == 'diffCur' &&
                                  cur != null &&
                                  v.versionNum != cur.versionNum) {
                                await _openDiff(v, cur);
                              } else if (action == 'restore') {
                                await _restore(v);
                              }
                            },
                            itemBuilder: (ctx) => [
                              const PopupMenuItem(value: 'preview', child: Text('View Markdown')),
                              if (prev != null)
                                const PopupMenuItem(
                                  value: 'diffPrev',
                                  child: Text('Diff vs previous'),
                                ),
                              if (cur != null && v.versionNum != cur.versionNum)
                                const PopupMenuItem(
                                  value: 'diffCur',
                                  child: Text('Diff vs current'),
                                ),
                              const PopupMenuItem(value: 'restore', child: Text('Restore via editor…')),
                            ],
                          ),
                        );
                      },
                    ),
    );
  }
}

class _SopVersionDiffPage extends StatelessWidget {
  const _SopVersionDiffPage({
    required this.labelA,
    required this.labelB,
    required this.bodyA,
    required this.bodyB,
  });

  final String labelA;
  final String labelB;
  final String bodyA;
  final String bodyB;

  @override
  Widget build(BuildContext context) {
    final lines = unifiedLineDiff(bodyA, bodyB);
    final theme = Theme.of(context);
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Compare versions'),
          bottom: TabBar(
            tabs: [
              Tab(text: 'Unified ($labelA → $labelB)'),
              const Tab(text: 'Side by side'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            ListView.builder(
              padding: const EdgeInsets.all(8),
              itemCount: lines.length,
              itemBuilder: (_, i) {
                final l = lines[i];
                final prefix = switch (l.kind) {
                  DiffLineKind.same => ' ',
                  DiffLineKind.removed => '-',
                  DiffLineKind.added => '+',
                };
                final Color? bg = switch (l.kind) {
                  DiffLineKind.same => null,
                  DiffLineKind.removed =>
                    theme.colorScheme.errorContainer.withOpacity(0.35),
                  DiffLineKind.added =>
                    theme.colorScheme.primaryContainer.withOpacity(0.4),
                };
                return Container(
                  color: bg,
                  padding: const EdgeInsets.symmetric(vertical: 2, horizontal: 4),
                  child: SelectableText(
                    '$prefix ${l.text}',
                    style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
                  ),
                );
              },
            ),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Material(
                        color: theme.colorScheme.surfaceContainerHighest,
                        child: Padding(
                          padding: const EdgeInsets.all(8),
                          child: Text(labelA, style: theme.textTheme.titleSmall),
                        ),
                      ),
                      Expanded(
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(8),
                          child: SelectableText(
                            bodyA,
                            style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const VerticalDivider(width: 1),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Material(
                        color: theme.colorScheme.surfaceContainerHighest,
                        child: Padding(
                          padding: const EdgeInsets.all(8),
                          child: Text(labelB, style: theme.textTheme.titleSmall),
                        ),
                      ),
                      Expanded(
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(8),
                          child: SelectableText(
                            bodyB,
                            style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
