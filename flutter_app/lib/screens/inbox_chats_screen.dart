import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/chat_models.dart';
import '../state/session_controller.dart';
import 'chat_detail_screen.dart';

enum _InboxFilter { all, mine, unassigned, humanQueue }

class InboxChatsScreen extends StatefulWidget {
  const InboxChatsScreen({super.key});

  @override
  State<InboxChatsScreen> createState() => _InboxChatsScreenState();
}

class _InboxChatsScreenState extends State<InboxChatsScreen> {
  final _search = TextEditingController();
  _InboxFilter _filter = _InboxFilter.all;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  String? _assignedParam() {
    switch (_filter) {
      case _InboxFilter.all:
      case _InboxFilter.humanQueue:
        return null;
      case _InboxFilter.mine:
        return 'me';
      case _InboxFilter.unassigned:
        return 'unassigned';
    }
  }

  String? _stateParam() {
    return null;
  }

  Future<void> _reloadList(SessionController session) async {
    session.bumpInboxGeneration();
  }

  String _stateLabel(String state) {
    switch (state) {
      case 'HUMAN_REQ':
        return 'Needs human';
      case 'WAITING_OWNER_DATA':
        return 'Needs your info';
      case 'AGENT_ACTIVE':
        return 'Agent chatting';
      case 'AI_ACTIVE':
        return 'AI chatting';
      case 'CLOSED':
        return 'Closed';
      default:
        return state;
    }
  }

  String _activitySubtitle(ChatListItem c) {
    final t = c.lastCustomerMsgAt ?? c.lastOutboundAt ?? c.createdAt;
    final rel = DateFormat.MMMd().add_Hm().format(t.toLocal());
    final assign = c.assignedAgentId != null ? ' · Assigned' : ' · Unassigned';
    final pause = c.aiPausedUntil != null && c.aiPausedUntil!.isAfter(DateTime.now())
        ? ' · AI paused until ${DateFormat.MMMd().add_Hm().format(c.aiPausedUntil!.toLocal())}'
        : '';
    return '${_stateLabel(c.state)}$assign · $rel · ${c.lastMessagePreview ?? '—'}$pause';
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final user = session.user;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (user != null && user.isAgent)
          Material(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Text(
                'Agent: use the Mine filter for chats assigned to you. '
                'You can only reply when you are the active assignee.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _search,
                  decoration: InputDecoration(
                    hintText: 'Search phone…',
                    border: const OutlineInputBorder(),
                    isDense: true,
                    suffixIcon: IconButton(
                      tooltip: 'Search',
                      icon: const Icon(Icons.search),
                      onPressed: () =>
                          setState(() => session.bumpInboxGeneration()),
                    ),
                  ),
                  onSubmitted: (_) =>
                      setState(() => session.bumpInboxGeneration()),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton.tonalIcon(
                onPressed: () => _reloadList(session),
                icon: const Icon(Icons.refresh, size: 20),
                label: const Text('Refresh'),
              ),
            ],
          ),
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Row(
            children: [
              FilterChip(
                label: const Text('All'),
                selected: _filter == _InboxFilter.all,
                onSelected: (_) => setState(() => _filter = _InboxFilter.all),
              ),
              const SizedBox(width: 6),
              FilterChip(
                label: const Text('Mine'),
                selected: _filter == _InboxFilter.mine,
                onSelected: (_) => setState(() => _filter = _InboxFilter.mine),
              ),
              const SizedBox(width: 6),
              FilterChip(
                label: const Text('Unassigned'),
                selected: _filter == _InboxFilter.unassigned,
                onSelected: (_) => setState(() => _filter = _InboxFilter.unassigned),
              ),
              const SizedBox(width: 6),
              FilterChip(
                label: const Text('Needs human'),
                selected: _filter == _InboxFilter.humanQueue,
                onSelected: (_) =>
                    setState(() => _filter = _InboxFilter.humanQueue),
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<ChatListItem>>(
            key: ValueKey<int>(session.inboxGeneration),
            future: session.api.listChats(
              token: session.token!,
              user: session.user!,
              assigned: _assignedParam(),
              state: _stateParam(),
              humanQueue: _filter == _InboxFilter.humanQueue,
              phoneQuery:
                  _search.text.trim().isEmpty ? null : _search.text.trim(),
            ),
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snap.hasError) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text('${snap.error}', textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        FilledButton.tonal(
                          onPressed: () => setState(() {}),
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              }
              final items = snap.data ?? const <ChatListItem>[];
              if (items.isEmpty) {
                return RefreshIndicator(
                  onRefresh: () => _reloadList(session),
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: const [
                      SizedBox(height: 120),
                      Center(child: Text('No chats match this filter.')),
                    ],
                  ),
                );
              }
              return RefreshIndicator(
                onRefresh: () => _reloadList(session),
                child: ListView.separated(
                  physics: const AlwaysScrollableScrollPhysics(),
                  itemCount: items.length,
                  separatorBuilder: (context, index) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final c = items[i];
                    return ListTile(
                      leading: _StateDot(state: c.state),
                      title: Text(c.customerPhone),
                      subtitle: Text(
                        _activitySubtitle(c),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => ChatDetailScreen(
                              chatId: c.id,
                              title: c.customerPhone,
                            ),
                          ),
                        );
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

class _StateDot extends StatelessWidget {
  const _StateDot({required this.state});

  final String state;

  Color _color(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    switch (state) {
      case 'HUMAN_REQ':
        return cs.error;
      case 'WAITING_OWNER_DATA':
        return cs.secondary;
      case 'AGENT_ACTIVE':
        return cs.primary;
      case 'AI_ACTIVE':
        return cs.tertiary;
      case 'CLOSED':
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
