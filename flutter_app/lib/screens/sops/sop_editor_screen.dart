import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../state/session_controller.dart';
import '../../utils/ops_api_auth.dart';
import '../../widgets/safe_markdown_body.dart';

class SopEditorScreen extends StatefulWidget {
  const SopEditorScreen({
    super.key,
    this.sopId,
    this.initialBodyOverride,
  });

  /// Create new SOP (POST).
  const SopEditorScreen.create({super.key})
      : sopId = null,
        initialBodyOverride = null;

  /// Edit existing (GET + PUT).
  SopEditorScreen.edit({super.key, required String sopId})
      : sopId = sopId,
        initialBodyOverride = null;

  /// Restore: open editor with body from an older version (still PUT as new version).
  SopEditorScreen.restore({
    super.key,
    required String sopId,
    required String body,
  })  : sopId = sopId,
        initialBodyOverride = body;

  final String? sopId;
  final String? initialBodyOverride;

  @override
  State<SopEditorScreen> createState() => _SopEditorScreenState();
}

class _SopEditorScreenState extends State<SopEditorScreen> {
  final _formKey = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _slug = TextEditingController();
  final _category = TextEditingController();
  final _body = TextEditingController();
  String _status = 'active';
  bool _loading = true;
  bool _saving = false;
  Object? _error;

  static final _slugRe = RegExp(r'^[a-z0-9][a-z0-9_-]*$');

  bool get _isCreate => widget.sopId == null;

  void _onBodyChanged() {
    if (mounted) setState(() {});
  }

  @override
  void initState() {
    super.initState();
    _body.addListener(_onBodyChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _body.removeListener(_onBodyChanged);
    _title.dispose();
    _slug.dispose();
    _category.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_isCreate) {
      setState(() {
        _loading = false;
        if (widget.initialBodyOverride != null) {
          _body.text = widget.initialBodyOverride!;
        }
      });
      return;
    }
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final d = await session.opsApi.getSop(token: token, sopId: widget.sopId!);
      _title.text = d.title;
      _slug.text = d.slug;
      _category.text = d.category ?? '';
      _status = d.status;
      _body.text = widget.initialBodyOverride ?? d.bodyMarkdown;
      setState(() => _loading = false);
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

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final session = context.read<SessionController>();
    final token = session.token;
    if (token == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      if (_isCreate) {
        await session.opsApi.createSop(
          token: token,
          body: {
            'title': _title.text.trim(),
            'slug': _slug.text.trim().toLowerCase(),
            'category': _category.text.trim().isEmpty ? null : _category.text.trim(),
            'status': _status,
            'body_markdown': _body.text,
          },
        );
      } else {
        await session.opsApi.updateSop(
          token: token,
          sopId: widget.sopId!,
          body: {
            'title': _title.text.trim(),
            'category': _category.text.trim().isEmpty ? null : _category.text.trim(),
            'status': _status,
            'body_markdown': _body.text,
          },
        );
      }
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      if (handleOpsUnauthorizedAndForbidden(
        context,
        e,
        onMessage: (m) => setState(() => _error = m),
      )) {
        setState(() => _saving = false);
        return;
      }
      setState(() {
        _error = e.toString();
        _saving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(_isCreate ? 'New SOP' : 'Edit SOP')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(_isCreate ? 'New SOP' : 'Edit SOP'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Fields'),
              Tab(text: 'Preview'),
            ],
          ),
          actions: [
            TextButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save'),
            ),
          ],
        ),
        body: Form(
          key: _formKey,
          child: TabBarView(
            children: [
              ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        '$_error',
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                    ),
                  TextFormField(
                    controller: _title,
                    decoration: const InputDecoration(
                      labelText: 'Title',
                      border: OutlineInputBorder(),
                    ),
                    validator: (v) =>
                        v == null || v.trim().isEmpty ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _slug,
                    decoration: const InputDecoration(
                      labelText: 'Slug (create only)',
                      border: OutlineInputBorder(),
                      helperText: 'lowercase letters, digits, _ and -',
                    ),
                    enabled: _isCreate,
                    validator: (v) {
                      if (!_isCreate) return null;
                      if (v == null || v.trim().isEmpty) return 'Required';
                      if (!_slugRe.hasMatch(v.trim())) return 'Invalid slug';
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _category,
                    decoration: const InputDecoration(
                      labelText: 'Category (optional)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: _status,
                    decoration: const InputDecoration(
                      labelText: 'Status',
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'active', child: Text('active')),
                      DropdownMenuItem(value: 'archived', child: Text('archived')),
                    ],
                    onChanged: (v) {
                      if (v != null) setState(() => _status = v);
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _body,
                    decoration: const InputDecoration(
                      labelText: 'Body (Markdown)',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                    minLines: 16,
                    maxLines: 40,
                    validator: (v) =>
                        v == null || v.trim().isEmpty ? 'Body required' : null,
                  ),
                ],
              ),
              ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    'CommonMark preview (raw HTML in Markdown is not enabled).',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 12),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: SafeMarkdownBody(
                        data: _body.text.trim().isEmpty
                            ? '_Nothing to preview yet._'
                            : _body.text,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
