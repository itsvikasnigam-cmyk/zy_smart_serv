import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/chat_models.dart';
import '../models/user_model.dart';
import '../state/session_controller.dart';

enum _ChatMenuAction { reassign, unassign, escalateQueue, escalateToAgent }

class ChatDetailScreen extends StatefulWidget {
  const ChatDetailScreen({
    super.key,
    required this.chatId,
    required this.title,
  });

  final String chatId;
  final String title;

  @override
  State<ChatDetailScreen> createState() => _ChatDetailScreenState();
}

class _ChatDetailScreenState extends State<ChatDetailScreen> {
  final _composer = TextEditingController();
  Timer? _typingTimer;
  bool _sending = false;
  SessionController? _session;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _session ??= context.read<SessionController>();
  }

  @override
  void dispose() {
    _typingTimer?.cancel();
    unawaited(_sendTypingStopped());
    _composer.dispose();
    super.dispose();
  }

  Future<void> _sendTypingStopped() async {
    final session = _session;
    if (session == null || !session.isLoggedIn || !session.usesTenantInbox) {
      return;
    }
    try {
      await session.api.postTyping(
        token: session.token!,
        user: session.user!,
        chatId: widget.chatId,
        state: 'stopped',
      );
    } catch (_) {}
  }

  void _onComposerChanged(String text, SessionController session) {
    if (!session.usesTenantInbox) return;
    _typingTimer?.cancel();
    if (text.trim().isEmpty) return;
    _typingTimer = Timer(const Duration(milliseconds: 500), () async {
      try {
        await session.api.postTyping(
          token: session.token!,
          user: session.user!,
          chatId: widget.chatId,
          state: 'typing',
          ttlSeconds: 8,
        );
      } catch (_) {}
    });
  }

  Future<void> _send(SessionController session) async {
    final body = _composer.text.trim();
    if (body.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      await session.api.postReply(
        token: session.token!,
        user: session.user!,
        chatId: widget.chatId,
        text: body,
      );
      _composer.clear();
      session.bumpInboxGeneration();
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e')),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<UserModel?> _pickAgentUser(
    BuildContext context,
    SessionController session, {
    required String title,
  }) async {
    final agents = await session.api.listUsers(
      token: session.token!,
      user: session.user!,
      role: 'agent',
    );
    if (!context.mounted) return null;
    if (agents.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No agents in this client.')),
      );
      return null;
    }
    return showDialog<UserModel>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text(title),
        children: [
          for (final a in agents)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(ctx, a),
              child: Text(a.email ?? a.name ?? a.id),
            ),
        ],
      ),
    );
  }

  Future<void> _applyAssignOrReassign(
    BuildContext context,
    SessionController session,
    UserModel agent, {
    required bool hasActiveAssignment,
  }) async {
    try {
      if (hasActiveAssignment) {
        await session.api.postReassign(
          token: session.token!,
          user: session.user!,
          chatId: widget.chatId,
          assigneeUserId: agent.id,
        );
      } else {
        await session.api.postAssign(
          token: session.token!,
          user: session.user!,
          chatId: widget.chatId,
          assigneeUserId: agent.id,
        );
      }
      session.bumpInboxGeneration();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Assigned to ${agent.email ?? agent.id}')),
        );
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e')),
        );
      }
    }
  }

  Future<void> _unassignChat(BuildContext context, SessionController session) async {
    try {
      await session.api.postUnassign(
        token: session.token!,
        user: session.user!,
        chatId: widget.chatId,
      );
      session.bumpInboxGeneration();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Returned chat to queue')),
        );
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e')),
        );
      }
    }
  }

  Future<void> _escalateToQueue(BuildContext context, SessionController session) async {
    try {
      await session.api.postEscalate(
        token: session.token!,
        user: session.user!,
        chatId: widget.chatId,
      );
      session.bumpInboxGeneration();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Escalated to agent queue')),
        );
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final timeFmt = DateFormat.Hm();
    final isOwner = session.user?.isOwner ?? false;
    final isAgent = session.user?.isAgent ?? false;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          if (isOwner)
            IconButton(
              tooltip: 'Assign to agent',
              icon: const Icon(Icons.group_add_outlined),
              onPressed: () async {
                try {
                  final chosen = await _pickAgentUser(
                    context,
                    session,
                    title: 'Assign to agent',
                  );
                  if (chosen != null && context.mounted) {
                    final d = await session.api.chatDetail(
                      token: session.token!,
                      user: session.user!,
                      chatId: widget.chatId,
                    );
                    final has = d.assignment != null &&
                        d.assignment!['status'] == 'ACTIVE';
                    if (!context.mounted) return;
                    await _applyAssignOrReassign(
                      context,
                      session,
                      chosen,
                      hasActiveAssignment: has,
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('$e')),
                    );
                  }
                }
              },
            ),
          if (isOwner || isAgent)
            PopupMenuButton<_ChatMenuAction>(
              tooltip: 'Chat actions',
              onSelected: (action) async {
                switch (action) {
                  case _ChatMenuAction.reassign:
                    if (!isOwner) return;
                    final chosen = await _pickAgentUser(
                      context,
                      session,
                      title: 'Reassign to agent',
                    );
                    if (chosen == null || !context.mounted) return;
                    await _applyAssignOrReassign(
                      context,
                      session,
                      chosen,
                      hasActiveAssignment: true,
                    );
                    return;
                  case _ChatMenuAction.unassign:
                    await _unassignChat(context, session);
                    return;
                  case _ChatMenuAction.escalateQueue:
                    await _escalateToQueue(context, session);
                    return;
                  case _ChatMenuAction.escalateToAgent:
                    final chosen = await _pickAgentUser(
                      context,
                      session,
                      title: 'Escalate to agent',
                    );
                    if (chosen == null || !context.mounted) return;
                    try {
                      await session.api.postEscalate(
                        token: session.token!,
                        user: session.user!,
                        chatId: widget.chatId,
                        toUserId: chosen.id,
                        reason: 'escalated',
                      );
                      session.bumpInboxGeneration();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              'Escalated to ${chosen.email ?? chosen.id}',
                            ),
                          ),
                        );
                      }
                      if (mounted) setState(() {});
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('$e')),
                        );
                      }
                    }
                    return;
                }
              },
              itemBuilder: (ctx) {
                final entries = <PopupMenuEntry<_ChatMenuAction>>[];
                if (isOwner) {
                  entries.add(
                    const PopupMenuItem(
                      value: _ChatMenuAction.reassign,
                      child: Text('Reassign to agent…'),
                    ),
                  );
                }
                entries.addAll([
                  const PopupMenuItem(
                    value: _ChatMenuAction.escalateQueue,
                    child: Text('Return to agent queue'),
                  ),
                  const PopupMenuItem(
                    value: _ChatMenuAction.escalateToAgent,
                    child: Text('Escalate to specific agent…'),
                  ),
                ]);
                if (isOwner) {
                  entries.add(
                    const PopupMenuItem(
                      value: _ChatMenuAction.unassign,
                      child: Text('Unassign (release)'),
                    ),
                  );
                }
                return entries;
              },
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: FutureBuilder<ChatDetail>(
              key: ValueKey<int>(session.inboxGeneration),
              future: session.api.chatDetail(
                token: session.token!,
                user: session.user!,
                chatId: widget.chatId,
              ),
              builder: (context, snap) {
                if (snap.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snap.hasError) {
                  return Center(child: Text('${snap.error}'));
                }
                final detail = snap.data!;
                final assign = detail.assignment;
                final rows = <_Row>[];
                for (final m in detail.pendingOutbound) {
                  rows.add(_Row.pending(m));
                }
                for (final m in detail.messages) {
                  rows.add(_Row.message(m));
                }
                rows.sort((a, b) => a.timestamp.compareTo(b.timestamp));
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (assign != null)
                      MaterialBanner(
                        content: Text(
                          'Assignment ${assign['status']}: '
                          'agent ${assign['assigned_to_user_id']}',
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => session.bumpInboxGeneration(),
                            child: const Text('Refresh'),
                          ),
                        ],
                      ),
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        itemCount: rows.length,
                        itemBuilder: (context, i) {
                          final r = rows[i];
                          return Align(
                            alignment: r.outbound
                                ? Alignment.centerRight
                                : Alignment.centerLeft,
                            child: ConstrainedBox(
                              constraints: BoxConstraints(
                                maxWidth: MediaQuery.sizeOf(context).width * 0.86,
                              ),
                              child: Card(
                                color: r.pending
                                    ? Theme.of(context).colorScheme.surfaceContainerHighest
                                    : null,
                                child: Padding(
                                  padding: const EdgeInsets.all(10),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        r.title,
                                        style: Theme.of(context).textTheme.labelMedium,
                                      ),
                                      const SizedBox(height: 4),
                                      SelectableText(r.body),
                                      const SizedBox(height: 4),
                                      Text(
                                        timeFmt.format(r.timestamp.toLocal()),
                                        style: Theme.of(context).textTheme.labelSmall,
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _composer,
                    minLines: 1,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      hintText: 'Reply…',
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (t) => _onComposerChanged(t, session),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _sending ? null : () => _send(session),
                  child: _sending
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Row {
  _Row._({
    required this.timestamp,
    required this.outbound,
    required this.pending,
    required this.title,
    required this.body,
  });

  factory _Row.message(InboxMessage m) {
    final outbound = m.direction == 'out';
    final title = '${m.sender} · ${m.source ?? ''}'
        '${m.outboxKind != null ? ' · ${m.outboxKind}' : ''}';
    return _Row._(
      timestamp: m.timestamp,
      outbound: outbound,
      pending: false,
      title: title.trim(),
      body: m.text,
    );
  }

  factory _Row.pending(InboxMessage m) {
    return _Row._(
      timestamp: m.timestamp,
      outbound: true,
      pending: true,
      title: 'Pending outbound · ${m.outboxKind ?? ''} · ${m.outboxStatus ?? ''}',
      body: m.text,
    );
  }

  final DateTime timestamp;
  final bool outbound;
  final bool pending;
  final String title;
  final String body;
}
