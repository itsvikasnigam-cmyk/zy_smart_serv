import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../services/ops_api_repository.dart';
import '../state/session_controller.dart';
import '../utils/ops_api_auth.dart';

/// M8 control plane — edits **`ops_runtime_config`** via **`ops_api`** GET/PUT `/ops/runtime-config/{key}`.
class SuperAdminControlPlaneScreen extends StatefulWidget {
  const SuperAdminControlPlaneScreen({super.key});

  @override
  State<SuperAdminControlPlaneScreen> createState() =>
      _SuperAdminControlPlaneScreenState();
}

class _SuperAdminControlPlaneScreenState
    extends State<SuperAdminControlPlaneScreen> {
  bool _loading = true;
  String? _error;

  final _debounceSec = TextEditingController();
  final _debounceMax = TextEditingController();
  final _adaptiveBurst = TextEditingController();
  bool _adaptiveEnabled = true;

  final _urgentJson = TextEditingController();

  bool _fallbackEnabled = false;
  bool _fallbackJudge = false;
  final _fallbackThreshold = TextEditingController();
  final _fallbackPrimaryTok = TextEditingController();
  final _fallbackJudgeTok = TextEditingController();
  final _fallbackDailyCap = TextEditingController();

  final _needsOwnerReply = TextEditingController();
  bool _typingHardLock = false;

  final _pricingUpiMinor = TextEditingController();
  final _pricingCardMinor = TextEditingController();
  String _pricingCurrency = 'INR';

  @override
  void initState() {
    super.initState();
    _pricingUpiMinor.addListener(_onPricingFieldChanged);
    _pricingCardMinor.addListener(_onPricingFieldChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadAll());
  }

  void _onPricingFieldChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _debounceSec.dispose();
    _debounceMax.dispose();
    _adaptiveBurst.dispose();
    _urgentJson.dispose();
    _fallbackThreshold.dispose();
    _fallbackPrimaryTok.dispose();
    _fallbackJudgeTok.dispose();
    _fallbackDailyCap.dispose();
    _needsOwnerReply.dispose();
    _pricingUpiMinor.removeListener(_onPricingFieldChanged);
    _pricingCardMinor.removeListener(_onPricingFieldChanged);
    _pricingUpiMinor.dispose();
    _pricingCardMinor.dispose();
    super.dispose();
  }

  Future<Object?> _getJson(String key) async {
    final session = context.read<SessionController>();
    final t = session.token;
    if (t == null) return null;
    try {
      final e = await session.opsApi.getRuntimeConfig(token: t, key: key);
      return e.valueJson;
    } catch (e) {
      if (e is OpsApiException && e.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<void> _put(String key, Object? value, {String? snack}) async {
    final session = context.read<SessionController>();
    final t = session.token;
    if (t == null) return;
    try {
      await session.opsApi.putRuntimeConfig(
        token: t,
        key: key,
        valueJson: value,
        reason: 'flutter_control_plane',
      );
      if (mounted && snack != null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(snack)));
      }
    } catch (e) {
      if (!handleOpsUnauthorizedAndForbidden(
        context,
        e,
        onMessage: (m) =>
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m))),
      )) {
        rethrow;
      }
    }
  }

  Future<void> _loadAll() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final sec = await _getJson('debounce.seconds');
      final max = await _getJson('debounce.max_seconds');
      final adaptOn = await _getJson('debounce.adaptive.enabled');
      final burst = await _getJson('debounce.adaptive.two_msgs_within_sec');
      final urgent = await _getJson('ai.urgent_bypass_substrings');
      final fbOn = await _getJson('ai.fallback.enabled');
      final fbJudge = await _getJson('ai.fallback.use_judge');
      final fbThr = await _getJson('ai.fallback.quality_threshold');
      final fbPt = await _getJson('ai.fallback.max_primary_tokens');
      final fbJt = await _getJson('ai.fallback.max_judge_tokens');
      final fbCap = await _getJson('ai.fallback.max_calls_per_client_per_day');
      final owner = await _getJson('ai.needs_owner_data_customer_reply');
      final hardLock = await _getJson('inbox.typing_hard_lock_enabled');
      final priceCur = await _getJson('pricing.in.currency');
      final priceUpi = await _getJson('pricing.in.upi_minor_units');
      final priceCard = await _getJson('pricing.in.card_minor_units');

      _debounceSec.text = '${_asInt(sec, 3)}';
      _debounceMax.text = '${_asInt(max, 10)}';
      _adaptiveEnabled = _asBool(adaptOn, true);
      _adaptiveBurst.text = '${_asInt(burst, 2)}';
      _urgentJson.text = const JsonEncoder.withIndent('  ').convert(
        urgent is List ? urgent : (urgent ?? []),
      );
      _fallbackEnabled = _asBool(fbOn, false);
      _fallbackJudge = _asBool(fbJudge, false);
      _fallbackThreshold.text = '${_asDouble(fbThr, 0.65)}';
      _fallbackPrimaryTok.text = '${_asInt(fbPt, 512)}';
      _fallbackJudgeTok.text = '${_asInt(fbJt, 256)}';
      _fallbackDailyCap.text = '${_asInt(fbCap, 200)}';
      if (owner is String) {
        _needsOwnerReply.text = owner;
      } else if (owner != null) {
        _needsOwnerReply.text = jsonEncode(owner);
      }
      _typingHardLock = _asBool(hardLock, false);
      if (priceCur is String && priceCur.isNotEmpty) {
        _pricingCurrency = priceCur;
      }
      _pricingUpiMinor.text = '${_asInt(priceUpi, 49900)}';
      _pricingCardMinor.text = '${_asInt(priceCard, 59900)}';
    } catch (e) {
      _error = e.toString();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  int _asInt(Object? v, int d) {
    if (v is int) return v;
    if (v is num) return v.toInt();
    if (v is String) return int.tryParse(v) ?? d;
    return d;
  }

  double _asDouble(Object? v, double d) {
    if (v is double) return v;
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v) ?? d;
    return d;
  }

  bool _asBool(Object? v, bool d) {
    if (v is bool) return v;
    if (v is String) {
      final s = v.toLowerCase();
      if (s == 'true' || s == '1') return true;
      if (s == 'false' || s == '0') return false;
    }
    return d;
  }

  Future<void> _saveDebounce() async {
    await _put('debounce.seconds', int.parse(_debounceSec.text.trim()));
    await _put('debounce.max_seconds', int.parse(_debounceMax.text.trim()));
    await _put('debounce.adaptive.enabled', _adaptiveEnabled);
    await _put(
      'debounce.adaptive.two_msgs_within_sec',
      int.parse(_adaptiveBurst.text.trim()),
    );
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Debounce settings saved')),
      );
    }
  }

  Future<void> _saveUrgent() async {
    final parsed = jsonDecode(_urgentJson.text) as List<dynamic>;
    await _put('ai.urgent_bypass_substrings', parsed);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Urgent bypass list saved')),
      );
    }
  }

  Future<void> _saveFallback() async {
    await _put('ai.fallback.enabled', _fallbackEnabled);
    await _put('ai.fallback.use_judge', _fallbackJudge);
    await _put(
      'ai.fallback.quality_threshold',
      double.parse(_fallbackThreshold.text.trim()),
    );
    await _put(
      'ai.fallback.max_primary_tokens',
      int.parse(_fallbackPrimaryTok.text.trim()),
    );
    await _put(
      'ai.fallback.max_judge_tokens',
      int.parse(_fallbackJudgeTok.text.trim()),
    );
    await _put(
      'ai.fallback.max_calls_per_client_per_day',
      int.parse(_fallbackDailyCap.text.trim()),
    );
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('AI fallback settings saved')),
      );
    }
  }

  Future<void> _saveNeedsOwner() async {
    final t = _needsOwnerReply.text.trim();
    Object? val = t;
    if (t.startsWith('{') || t.startsWith('[')) {
      val = jsonDecode(t);
    }
    await _put('ai.needs_owner_data_customer_reply', val);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Needs-owner reply saved')),
      );
    }
  }

  String _rupeesPreview(String minorText) {
    final minor = int.tryParse(minorText.trim());
    if (minor == null) return '—';
    return '₹${(minor / 100).toStringAsFixed(2)}';
  }

  Future<void> _savePricing() async {
    await _put('pricing.in.currency', _pricingCurrency);
    await _put('pricing.in.upi_minor_units', int.parse(_pricingUpiMinor.text.trim()));
    await _put('pricing.in.card_minor_units', int.parse(_pricingCardMinor.text.trim()));
    if (mounted) {
      setState(() {});
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Pricing saved — UPI ${_rupeesPreview(_pricingUpiMinor.text)}, '
            'Card ${_rupeesPreview(_pricingCardMinor.text)}',
          ),
        ),
      );
    }
  }

  Future<void> _saveInbox() async {
    await _put('inbox.typing_hard_lock_enabled', _typingHardLock);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Inbox settings saved')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Failed to load config', style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(onPressed: _loadAll, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Control plane', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(
          'Writes go to ops_api GET/PUT /ops/runtime-config/{key} (audit in ops_runtime_config_audit).',
          style: theme.textTheme.bodySmall,
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: _loadAll,
            icon: const Icon(Icons.refresh),
            label: const Text('Reload'),
          ),
        ),
        _section(
          context,
          title: 'Debounce & adaptive batching',
          child: Column(
            children: [
              _numField('debounce.seconds', _debounceSec),
              _numField('debounce.max_seconds', _debounceMax),
              SwitchListTile(
                title: const Text('debounce.adaptive.enabled'),
                value: _adaptiveEnabled,
                onChanged: (v) => setState(() => _adaptiveEnabled = v),
              ),
              _numField('debounce.adaptive.two_msgs_within_sec', _adaptiveBurst),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  onPressed: _saveDebounce,
                  child: const Text('Save debounce'),
                ),
              ),
            ],
          ),
        ),
        _section(
          context,
          title: 'Urgent bypass',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _urgentJson,
                maxLines: 6,
                decoration: const InputDecoration(
                  labelText: 'ai.urgent_bypass_substrings (JSON array)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _saveUrgent,
                child: const Text('Save urgent list'),
              ),
            ],
          ),
        ),
        _section(
          context,
          title: 'AI fallback (requires AI_LLM_API_KEY in env)',
          child: Column(
            children: [
              SwitchListTile(
                title: const Text('ai.fallback.enabled'),
                value: _fallbackEnabled,
                onChanged: (v) => setState(() => _fallbackEnabled = v),
              ),
              SwitchListTile(
                title: const Text('ai.fallback.use_judge'),
                value: _fallbackJudge,
                onChanged: (v) => setState(() => _fallbackJudge = v),
              ),
              _numField('ai.fallback.quality_threshold', _fallbackThreshold),
              _numField('ai.fallback.max_primary_tokens', _fallbackPrimaryTok),
              _numField('ai.fallback.max_judge_tokens', _fallbackJudgeTok),
              _numField(
                'ai.fallback.max_calls_per_client_per_day',
                _fallbackDailyCap,
              ),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  onPressed: _saveFallback,
                  child: const Text('Save AI fallback'),
                ),
              ),
            ],
          ),
        ),
        _section(
          context,
          title: 'NEEDS_OWNER customer copy',
          child: Column(
            children: [
              TextField(
                controller: _needsOwnerReply,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'ai.needs_owner_data_customer_reply',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _saveNeedsOwner,
                child: const Text('Save customer reply'),
              ),
            ],
          ),
        ),
        _section(
          context,
          title: 'Inbox',
          child: Column(
            children: [
              SwitchListTile(
                title: const Text('inbox.typing_hard_lock_enabled'),
                subtitle: const Text('Only assignee may reply when enabled'),
                value: _typingHardLock,
                onChanged: (v) => setState(() => _typingHardLock = v),
              ),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  onPressed: _saveInbox,
                  child: const Text('Save inbox'),
                ),
              ),
            ],
          ),
        ),
        _section(
          context,
          title: 'Pricing (India)',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Currency: $_pricingCurrency', style: theme.textTheme.bodyMedium),
              _numField('pricing.in.upi_minor_units (paise)', _pricingUpiMinor),
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  'Preview UPI: ${_rupeesPreview(_pricingUpiMinor.text)}',
                  style: theme.textTheme.titleSmall,
                ),
              ),
              _numField('pricing.in.card_minor_units (paise)', _pricingCardMinor),
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  'Preview Card: ${_rupeesPreview(_pricingCardMinor.text)}',
                  style: theme.textTheme.titleSmall,
                ),
              ),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  onPressed: _savePricing,
                  child: const Text('Save pricing'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _section(
    BuildContext context, {
    required String title,
    required Widget child,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        title: Text(title),
        initiallyExpanded: true,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: child,
          ),
        ],
      ),
    );
  }

  Widget _numField(String label, TextEditingController c) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: TextField(
        controller: c,
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))],
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }
}
