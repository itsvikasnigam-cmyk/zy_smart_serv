import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/sop_models.dart';
import '../../state/session_controller.dart';
import '../../utils/ops_api_auth.dart';
import 'sop_run_detail_screen.dart';

class SopRunsListScreen extends StatefulWidget {
  const SopRunsListScreen({super.key});

  @override
  State<SopRunsListScreen> createState() => _SopRunsListScreenState();
}

class _SopRunsListScreenState extends State<SopRunsListScreen> {
  List<RunLog>? _runs;
  String? _error;
  bool _loading = true;
  final _sopFilter = TextEditingController();
  final _clientFilter = TextEditingController();
  String? _triggerFilter;
  DateTime? _fromDate;
  DateTime? _toDate;

  @override
  void dispose() {
    _sopFilter.dispose();
    _clientFilter.dispose();
    super.dispose();
  }

  String? _fmtYmd(DateTime? d) {
    if (d == null) return null;
    return '${d.year.toString().padLeft(4, '0')}-'
        '${d.month.toString().padLeft(2, '0')}-'
        '${d.day.toString().padLeft(2, '0')}';
  }

  Future<void> _pickFrom() async {
    final now = DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: _fromDate ?? now,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year + 1),
    );
    if (d != null) setState(() => _fromDate = d);
  }

  Future<void> _pickTo() async {
    final now = DateTime.now();
    final d = await showDatePicker(
      context: context,
      initialDate: _toDate ?? now,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year + 1),
    );
    if (d != null) setState(() => _toDate = d);
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
      final list = await session.opsApi.listRuns(
        token: token,
        sopId: _sopFilter.text.trim().isEmpty ? null : _sopFilter.text.trim(),
        clientId: _clientFilter.text.trim().isEmpty ? null : _clientFilter.text.trim(),
        triggerType: _triggerFilter,
        fromDateYyyyMmDd: _fmtYmd(_fromDate),
        toDateYyyyMmDd: _fmtYmd(_toDate),
      );
      setState(() {
        _runs = list;
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
          _runs = null;
        });
        return;
      }
      setState(() {
        _error = e.toString();
        _loading = false;
        _runs = null;
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
        title: const Text('Run logs'),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.info_outline, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Server returns at most 500 runs per request (newest first). '
                        'Use UTC date filters to narrow the window.',
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: 220,
                  child: TextField(
                    controller: _sopFilter,
                    decoration: const InputDecoration(
                      labelText: 'SOP id',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onSubmitted: (_) => _load(),
                  ),
                ),
                SizedBox(
                  width: 200,
                  child: TextField(
                    controller: _clientFilter,
                    decoration: const InputDecoration(
                      labelText: 'client_id',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    onSubmitted: (_) => _load(),
                  ),
                ),
                DropdownButton<String?>(
                  value: _triggerFilter,
                  hint: const Text('Trigger'),
                  items: const [
                    DropdownMenuItem<String?>(value: null, child: Text('Any trigger')),
                    DropdownMenuItem(value: 'manual', child: Text('manual')),
                    DropdownMenuItem(value: 'auto', child: Text('auto')),
                    DropdownMenuItem(value: 'alert', child: Text('alert')),
                    DropdownMenuItem(value: 'scheduled', child: Text('scheduled')),
                    DropdownMenuItem(value: 'other', child: Text('other')),
                  ],
                  onChanged: (v) => setState(() => _triggerFilter = v),
                ),
                OutlinedButton(
                  onPressed: _pickFrom,
                  child: Text(_fromDate == null ? 'From date' : 'From ${_fmtYmd(_fromDate)}'),
                ),
                OutlinedButton(
                  onPressed: _pickTo,
                  child: Text(_toDate == null ? 'To date' : 'To ${_fmtYmd(_toDate)}'),
                ),
                TextButton(
                  onPressed: () {
                    setState(() {
                      _fromDate = null;
                      _toDate = null;
                      _triggerFilter = null;
                    });
                    _load();
                  },
                  child: const Text('Clear dates'),
                ),
                FilledButton.tonal(onPressed: _load, child: const Text('Apply')),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _runs == null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Text(
                            'Could not load runs.\nCheck OPS_API_BASE_URL and super_admin role.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.titleMedium,
                          ),
                        ),
                      )
                    : _runs!.isEmpty
                        ? Center(
                            child: Text(
                              'No runs for these filters.',
                              style: theme.textTheme.titleMedium,
                            ),
                          )
                        : ListView.separated(
                            itemCount: _runs!.length,
                            separatorBuilder: (_, __) => const Divider(height: 1),
                            itemBuilder: (context, i) {
                              final r = _runs![i];
                              return ListTile(
                                title: Text('Run ${r.id.substring(0, 8)}…'),
                                subtitle: Text(
                                  'SOP ${r.sopId.substring(0, 8)}… · v${r.sopVersionAtRun} · ${r.triggerType}\n'
                                  '${df.format(r.createdAt.toLocal())}',
                                ),
                                isThreeLine: true,
                                trailing: const Icon(Icons.chevron_right),
                                onTap: () {
                                  Navigator.of(context).push<void>(
                                    MaterialPageRoute(
                                      builder: (_) => SopRunDetailScreen(runId: r.id),
                                    ),
                                  );
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
