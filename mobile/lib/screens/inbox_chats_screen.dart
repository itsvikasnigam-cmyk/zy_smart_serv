import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/chat_models.dart';
import '../state/session_controller.dart';
import 'chat_thread_screen.dart';

class InboxChatsScreen extends StatelessWidget {
  const InboxChatsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();

    if (!session.superAdminReady) {
      return const Center(
        child: Text('Set client scope in Settings to load chats.'),
      );
    }

    return FutureBuilder<List<ChatListItem>>(
      key: ValueKey<int>(session.inboxGeneration),
      future: session.api.listChats(
        token: session.token!,
        user: session.user!,
        superClientId: session.superAdminClientId,
      ),
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return Center(child: Text('${snap.error}'));
        }
        final items = snap.data ?? const <ChatListItem>[];
        if (items.isEmpty) {
          return const Center(child: Text('No chats yet.'));
        }
        return ListView.separated(
          itemCount: items.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, i) {
            final c = items[i];
            return ListTile(
              leading: _StateDot(state: c.state),
              title: Text(c.customerPhone),
              subtitle: Text(
                '${c.state} · ${c.lastMessagePreview ?? '—'}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => ChatThreadScreen(
                      chatId: c.id,
                      title: c.customerPhone,
                    ),
                  ),
                );
              },
            );
          },
        );
      },
    );
  }
}

class _StateDot extends StatelessWidget {
  const _StateDot({required this.state});

  final String state;

  Color _color(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    switch (state) {
      case 'PENDING_AGENT':
        return cs.error;
      case 'AGENT_ACTIVE':
        return cs.primary;
      case 'AI_ACTIVE':
        return cs.tertiary;
      case 'RESOLVED':
        return cs.outline;
      default:
        return cs.secondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 8,
      backgroundColor: _color(context),
    );
  }
}
