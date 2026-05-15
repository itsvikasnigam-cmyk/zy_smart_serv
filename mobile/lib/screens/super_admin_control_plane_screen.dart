import 'package:flutter/material.dart';

/// Read-only **M8 interactive control plane** — checklist § M8 panels.
///
/// **Writes** (runtime config editor, pricing, debounce, urgent, AI fallback) require
/// **Stem-approved** authenticated admin APIs on **`client_api`** (or a dedicated admin API).
/// Do **not** POST invented paths to **`ops_runtime_config`** from Flutter.
///
/// **M9 phase-2 / optional (checklist):** auto-trigger SOP runs, day-1 seed content, optional PDF —
/// UI hooks and **deep links** stay reserved until **Stem + Chat I + Chat L** assign contracts.
class SuperAdminControlPlaneScreen extends StatelessWidget {
  const SuperAdminControlPlaneScreen({super.key});

  Widget _panel(
    BuildContext context, {
    required String title,
    required String keysHint,
    required String backendNeed,
  }) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(keysHint, style: theme.textTheme.bodySmall),
            const SizedBox(height: 8),
            Text(
              backendNeed,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Flutter (Chat H): read-only until OpenAPI lists GET/PUT (or PATCH) admin routes with validation + audit/revert per blueprint.',
              style: theme.textTheme.bodySmall?.copyWith(
                fontStyle: FontStyle.italic,
                color: theme.colorScheme.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Control plane (read-only)', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(
          'Blueprint § M8 interactive panels. Backend stays B / C / I / J / K / L — Chat H only consumes documented admin read/write APIs.',
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 20),
        _panel(
          context,
          title: 'Runtime config (`ops_runtime_config`)',
          keysHint: 'Examples: debounce.seconds, debounce.max_seconds, ai.urgent_bypass_substrings, '
              'ai.needs_owner_data_customer_reply, usage.daily_inbound_limits, ai.fallback.*',
          backendNeed:
              'Needs: typed key/value API, server-side validation, last editor + timestamp, '
              'and revert using ops_runtime_config_audit (blueprint). No client-side writes until then.',
        ),
        _panel(
          context,
          title: 'Pricing (India)',
          keysHint: 'Blueprint: `pricing.in.*` (minor units), live preview (“UPI = ₹X”).',
          backendNeed:
              'Needs: read + optional write routes backed by bill_plans / config store — not a generic POST to ops_runtime_config.',
        ),
        _panel(
          context,
          title: 'Debounce & adaptive batching',
          keysHint: 'Keys: debounce.*, debounce.adaptive.* (see HANDOFF / gateway slice).',
          backendNeed:
              'Needs: admin-safe read/write surface (same audit story as runtime config) so Flutter never invents gateway-only knobs.',
        ),
        _panel(
          context,
          title: 'Urgent bypass',
          keysHint: 'routing.urgent_* / ai.urgent_bypass_substrings — aligned with AI engine (Chat D).',
          backendNeed:
              'Needs: structured list endpoints (keywords + intents arrays) with RBAC; edits coordinated with Chat A + AI contract.',
        ),
        _panel(
          context,
          title: 'AI fallback & rate limits',
          keysHint: 'ai.fallback.*, max_rate_per_client — see `POST /ai/respond` contract in HANDOFF.',
          backendNeed:
              'Needs: admin GET/PUT for ai.fallback.* and rate caps with validation; mirror Chat D ops keys only.',
        ),
        const SizedBox(height: 24),
        Text('M9 — phase-2 & optional (no UI yet)', style: theme.textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          '• Auto-trigger: consume ops_alert_events (Chat L) + mapped SOP slug (alerts.sop_trigger_map, TBD) → '
          'POST /ops/sops/{id}/run with trigger_type=auto (Chat I). Deep links into run detail = Chat L sequencing.\n'
          '• Day-1 SOP seed: content / import — Stem or ops pipeline, not Flutter-only.\n'
          '• Optional PDF export for audits — only if Stem assigns.',
          style: theme.textTheme.bodySmall?.copyWith(height: 1.45),
        ),
        const SizedBox(height: 24),
        Text('Notes', style: theme.textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          'Super-admin charts for revenue / collections / backlog / geo: Dash tab (GET /dash/admin/*, Chat J). '
          'Polish + device smoke = Chat N / Stem.',
          style: theme.textTheme.bodySmall,
        ),
      ],
    );
  }
}
