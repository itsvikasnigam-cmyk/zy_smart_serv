import 'package:flutter/material.dart';

int dashAsInt(Object? v) {
  if (v == null) return 0;
  if (v is int) return v;
  if (v is num) return v.toInt();
  return int.tryParse(v.toString()) ?? 0;
}

/// Parses a JSON object into non-negative int counts (skips non-numeric values).
Map<String, int> dashIntMapFromJson(Object? v) {
  if (v is! Map) return {};
  final out = <String, int>{};
  for (final e in v.entries) {
    final n = dashAsInt(e.value);
    if (n >= 0) {
      out[e.key.toString()] = n;
    }
  }
  return out;
}

/// Horizontal bar chart for small string→count maps (admin dash aggregates).
class DashDictBarCard extends StatelessWidget {
  const DashDictBarCard({
    super.key,
    required this.title,
    required this.data,
    this.maxRows = 14,
    this.emptyHint = 'No rows yet.',
  });

  final String title;
  final Map<String, int> data;
  final int maxRows;
  final String emptyHint;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final entries = data.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final slice = entries.take(maxRows).toList();
    final maxVal = slice.isEmpty ? 1 : slice.map((e) => e.value).reduce((a, b) => a > b ? a : b);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            if (slice.isEmpty)
              Text(emptyHint, style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant))
            else
              ...slice.map((e) {
                final frac = maxVal <= 0 ? 0.0 : (e.value / maxVal).clamp(0.0, 1.0);
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              e.key,
                              style: theme.textTheme.bodySmall,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Text(
                            '${e.value}',
                            style: theme.textTheme.labelMedium?.copyWith(fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: frac,
                          minHeight: 8,
                          backgroundColor: theme.colorScheme.surfaceContainerHighest,
                        ),
                      ),
                    ],
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

/// Stacked summary for `hourly_system_last_24h`–shaped objects.
class DashMessageTotalsCard extends StatelessWidget {
  const DashMessageTotalsCard({super.key, required this.title, required this.raw});

  final String title;
  final Object? raw;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final m = dashIntMapFromJson(raw);
    final c = m['customer'] ?? 0;
    final a = m['ai'] ?? 0;
    final g = m['agent'] ?? 0;
    final s = m['system'] ?? 0;
    final total = c + a + g + s;
    if (total <= 0) {
      return Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: theme.textTheme.titleSmall),
              const SizedBox(height: 4),
              Text(
                'No hourly message rollups in the last window (metrics_hourly_system may be empty).',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      );
    }
    Widget seg(String label, int v, Color bg, Color fg) {
      final w = v / total;
      return Expanded(
        flex: (w * 1000).round().clamp(1, 1000),
        child: Tooltip(
          message: '$label: $v',
          child: Container(
            color: bg,
            alignment: Alignment.center,
            child: Text(
              v > 0 ? '$v' : '',
              style: theme.textTheme.labelSmall?.copyWith(color: fg, fontWeight: FontWeight.w600),
            ),
          ),
        ),
      );
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            SizedBox(
              height: 28,
              child: Row(
                children: [
                  if (c > 0) seg('Customer', c, theme.colorScheme.primaryContainer, theme.colorScheme.onPrimaryContainer),
                  if (a > 0) seg('AI', a, theme.colorScheme.secondaryContainer, theme.colorScheme.onSecondaryContainer),
                  if (g > 0) seg('Agent', g, theme.colorScheme.tertiaryContainer, theme.colorScheme.onTertiaryContainer),
                  if (s > 0) seg('System', s, theme.colorScheme.surfaceContainerHighest, theme.colorScheme.onSurface),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _LegendDot(color: theme.colorScheme.primaryContainer, label: 'Customer $c'),
                _LegendDot(color: theme.colorScheme.secondaryContainer, label: 'AI $a'),
                _LegendDot(color: theme.colorScheme.tertiaryContainer, label: 'Agent $g'),
                if (s > 0) _LegendDot(color: theme.colorScheme.surfaceContainerHighest, label: 'System $s'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

/// KPI chips for scalar fields on admin overview JSON.
class DashKpiRow extends StatelessWidget {
  const DashKpiRow({super.key, required this.items});

  final List<({String label, int value})> items;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: items.map((e) {
        return Chip(
          avatar: Icon(Icons.analytics_outlined, size: 18, color: theme.colorScheme.primary),
          label: Text('${e.label}: ${e.value}'),
        );
      }).toList(),
    );
  }
}
