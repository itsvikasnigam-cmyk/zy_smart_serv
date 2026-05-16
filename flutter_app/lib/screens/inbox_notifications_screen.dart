import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/chat_models.dart';
import '../services/client_api_repository.dart';
import '../state/session_controller.dart';
import 'chat_detail_screen.dart';

/// Owner/agent in-app alerts from `GET /inbox/notifications`.
class InboxNotificationsScreen extends StatefulWidget {
  const InboxNotificationsScreen({super.key});

  @override
  State<InboxNotificationsScreen> createState() =>
      _InboxNotificationsScreenState();
}

class _InboxNotificationsScreenState extends State<InboxNotificationsScreen> {
  bool _unreadOnly = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final session = context.read<SessionController>();
      if (session.token != null) {
        _load(session);
      }
    });
  }

  Future<void> _load(SessionController session) async {
    session.bumpNotificationsGeneration();
    await session.refreshUnreadNotificationCount();
  }

  Future<void> _createTestAlert(SessionController session) async {
    try {
      final out = await session.api.postDevTestNotification(
        token: session.token!,
        user: session.user!,
      );
      await _load(session);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            out['message']?.toString() ?? 'Test alert created.',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$e')),
      );
    }
  }

  Future<void> _markRead(
    SessionController session,
    InboxNotification n,
  ) async {
    if (n.readAt != null) return;
    await session.api.postNotificationRead(
      token: session.token!,
      user: session.user!,
      notificationId: n.id,
    );
    await _load(session);
  }

  Future<void> _markAllRead(
    SessionController session,
    List<InboxNotification> items,
  ) async {
    for (final n in items) {
      if (n.readAt == null) {
        await session.api.postNotificationRead(
          token: session.token!,
          user: session.user!,
          notificationId: n.id,
        );
      }
    }
    await _load(session);
  }

  IconData _iconForKind(String kind) {
    switch (kind) {
      case 'handoff':
      case 'human_required':
        return Icons.support_agent_outlined;
      case 'needs_owner_data':
        return Icons.help_outline;
      case 'assignment':
        return Icons.person_add_outlined;
      default:
        return Icons.notifications_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final theme = Theme.of(context);

    if (session.token == null || session.user == null) {
      return const Center(child: Text('Not signed in.'));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Material(
          color: theme.colorScheme.surfaceContainerHighest,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Alerts for your account',
                  style: theme.textTheme.titleMedium,
                ),
                const SizedBox(height: 4),
                Text(
                  'Handoffs and owner tasks appear here. Tap one to open the chat. '
                  'On Windows desktop, use the Refresh button (pull-down is for touch screens).',
                  style: theme.textTheme.bodySmall,
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    FilterChip(
                      label: const Text('Unread only'),
                      selected: _unreadOnly,
                      onSelected: (v) => setState(() => _unreadOnly = v),
                    ),
                    FilledButton.icon(
                      onPressed: () => _load(session),
                      icon: const Icon(Icons.refresh, size: 20),
                      label: const Text('Refresh list'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => _createTestAlert(session),
                      icon: const Icon(Icons.science_outlined, size: 20),
                      label: const Text('Create test alert'),
                    ),
                    if (session.wsConnected)
                      Text(
                        'Live updates on',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.primary,
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
        Expanded(
          child: FutureBuilder<List<InboxNotification>>(
            key: ValueKey(
              '${session.notificationsGeneration}|$_unreadOnly',
            ),
            future: session.api.listNotifications(
              token: session.token!,
              user: session.user!,
              unreadOnly: _unreadOnly,
            ),
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snap.hasError) {
                final err = snap.error;
                if (err is ApiUnauthorizedException) {
                  session.logout();
                  return const SizedBox.shrink();
                }
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text('$err', textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        FilledButton(
                          onPressed: () => _load(session),
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              }
              final items = snap.data ?? const <InboxNotification>[];
              final unread = items.where((n) => n.readAt == null).length;

              if (items.isEmpty) {
                return RefreshIndicator(
                  onRefresh: () => _load(session),
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: const [
                      SizedBox(height: 120),
                      Center(
                        child: Text(
                          'No notifications yet.\n'
                          'They appear when a chat needs a human or owner.',
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ],
                  ),
                );
              }

              return RefreshIndicator(
                onRefresh: () => _load(session),
                child: ListView.builder(
                  physics: const AlwaysScrollableScrollPhysics(),
                  itemCount: items.length + 1,
                  itemBuilder: (context, i) {
                    if (i == 0) {
                      return Padding(
                        padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
                        child: Row(
                          children: [
                            Text(
                              '${items.length} shown'
                              '${_unreadOnly ? '' : ' · $unread unread'}',
                              style: theme.textTheme.bodySmall,
                            ),
                            const Spacer(),
                            if (unread > 0)
                              TextButton(
                                onPressed: () => _markAllRead(session, items),
                                child: const Text('Mark all read'),
                              ),
                          ],
                        ),
                      );
                    }
                    final n = items[i - 1];
                    final unreadRow = n.readAt == null;
                    return ListTile(
                      leading: Icon(
                        _iconForKind(n.kind),
                        color: unreadRow
                            ? theme.colorScheme.primary
                            : theme.colorScheme.outline,
                      ),
                      title: Text(
                        n.title,
                        style: unreadRow
                            ? theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w600,
                              )
                            : null,
                      ),
                      subtitle: Text(
                        [
                          if (n.body != null && n.body!.isNotEmpty) n.body!,
                          n.kind,
                          DateFormat.MMMd().add_jm().format(n.createdAt.toLocal()),
                        ].join(' · '),
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: unreadRow
                          ? Icon(
                              Icons.circle,
                              size: 10,
                              color: theme.colorScheme.primary,
                            )
                          : null,
                      onTap: () async {
                        if (unreadRow) {
                          await _markRead(session, n);
                        }
                        if (!context.mounted) return;
                        if (n.chatId != null && n.chatId!.isNotEmpty) {
                          await Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => ChatDetailScreen(
                                chatId: n.chatId!,
                                title: n.title,
                              ),
                            ),
                          );
                          if (context.mounted) {
                            await _load(session);
                          }
                        }
                      },
                    );
                  },
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}
