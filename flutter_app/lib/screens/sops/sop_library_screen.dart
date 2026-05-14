import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/sop_models.dart';
import '../../state/session_controller.dart';
import '../../utils/ops_api_auth.dart';
import 'sop_detail_screen.dart';
import 'sop_editor_screen.dart';

class SopLibraryScreen extends StatefulWidget {
  const SopLibraryScreen({super.key});

  @override
  State<SopLibraryScreen> createState() => _SopLibraryScreenState();
}

class _SopLibraryScreenState extends State<SopLibraryScreen> {
  final _search = TextEditingController();
  final _category = TextEditingController();
  String? _statusFilter; // null = all
  List<SopSummary>? _items;
  Object? _error;
  bool _loading = true;

  @override
  void dispose() {
    _search.dispose();
    _category.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final list = await session.opsApi.listSops(
        token: token,
        category: _category.text.trim().isEmpty ? null : _category.text.trim(),
        status: _statusFilter,
        q: _search.text.trim().isEmpty ? null : _search.text.trim(),
      );
      setState(() {
        _items = list;
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
          _items = null;
        });
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
        _items = null;
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('SOP library'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final created = await Navigator.of(context).push<bool>(
            MaterialPageRoute(
              builder: (_) => const SopEditorScreen.create(),
            ),
          );
          if (created == true && mounted) {
            await _load();
          }
        },
        icon: const Icon(Icons.add),
        label: const Text('New SOP'),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: 220,
                  child: TextField(
                    controller: _search,
                    decoration: const InputDecoration(
                      labelText: 'Search title',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onSubmitted: (_) => _load(),
                  ),
                ),
                SizedBox(
                  width: 160,
                  child: TextField(
                    controller: _category,
                    decoration: const InputDecoration(
                      labelText: 'Category',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onSubmitted: (_) => _load(),
                  ),
                ),
                Row(
                  children: [
                    FilterChip(
                      label: const Text('All statuses'),
                      selected: _statusFilter == null,
                      onSelected: (_) {
                        setState(() => _statusFilter = null);
                        _load();
                      },
                    ),
                    const SizedBox(width: 8),
                    FilterChip(
                      label: const Text('active'),
                      selected: _statusFilter == 'active',
                      onSelected: (_) {
                        setState(() => _statusFilter = 'active');
                        _load();
                      },
                    ),
                    const SizedBox(width: 8),
                    FilterChip(
                      label: const Text('archived'),
                      selected: _statusFilter == 'archived',
                      onSelected: (_) {
                        setState(() => _statusFilter = 'archived');
                        _load();
                      },
                    ),
                  ],
                ),
                FilledButton.tonal(
                  onPressed: _load,
                  child: const Text('Apply filters'),
                ),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                '$_error',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _items == null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Text(
                            'Could not load SOPs.\n'
                            'Check OPS_API_BASE_URL and that you are signed in as super_admin.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.titleMedium,
                          ),
                        ),
                      )
                    : _items!.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Text(
                            'No SOPs match these filters.\n'
                            'Try clearing search/category, or create one with + New SOP.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.titleMedium,
                          ),
                        ),
                      )
                    : ListView.separated(
                        itemCount: _items!.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (context, i) {
                          final s = _items![i];
                          return ListTile(
                            title: Text(s.title),
                            subtitle: Text(
                              '${s.slug} · v${s.currentVersion} · ${s.status}'
                              '${s.category != null ? ' · ${s.category}' : ''}',
                            ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () async {
                              final changed = await Navigator.of(context).push<bool>(
                                MaterialPageRoute(
                                  builder: (_) => SopDetailScreen(sopId: s.id),
                                ),
                              );
                              if (changed == true && mounted) {
                                await _load();
                              }
                            },
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
