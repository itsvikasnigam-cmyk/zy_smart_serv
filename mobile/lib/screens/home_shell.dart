import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';
import 'inbox_chats_screen.dart';
import 'settings_screen.dart';
import 'super_admin_ops_screen.dart';

class _TabSpec {
  const _TabSpec({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.page,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final Widget page;
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, this.initialTab = 0});

  final int initialTab;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  late int _index;

  @override
  void initState() {
    super.initState();
    _index = widget.initialTab;
  }

  List<_TabSpec> _tabsFor(bool isSuper) {
    return [
      _TabSpec(
        icon: Icons.inbox_outlined,
        selectedIcon: Icons.inbox,
        label: 'Inbox',
        page: const InboxChatsScreen(),
      ),
      if (isSuper)
        _TabSpec(
          icon: Icons.tune_outlined,
          selectedIcon: Icons.tune,
          label: 'Control plane',
          page: const SuperAdminOpsScreen(),
        ),
      _TabSpec(
        icon: Icons.settings_outlined,
        selectedIcon: Icons.settings,
        label: 'Settings',
        page: const SettingsScreen(),
      ),
    ];
  }

  String _title(List<_TabSpec> tabs, String role) {
    final t = tabs[_index];
    if (t.label == 'Inbox') return 'Inbox · $role';
    return t.label;
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final user = session.user!;
    final isSuper = user.isSuperAdmin;
    final tabs = _tabsFor(isSuper);
    _index = _index.clamp(0, tabs.length - 1);
    final banner = isSuper && !session.superAdminReady;

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 840;
        return Scaffold(
          appBar: AppBar(
            title: Text(_title(tabs, user.role)),
            actions: [
              IconButton(
                tooltip: 'Refresh inbox',
                onPressed: () => session.bumpInboxGeneration(),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: Column(
            children: [
              if (banner)
                MaterialBanner(
                  content: const Text(
                    'super_admin needs a tenant client_id (UUID). '
                    'Set it under Settings before inbox or WebSocket will work.',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () {
                        setState(() {
                          _index = tabs.indexWhere((t) => t.label == 'Settings');
                        });
                      },
                      child: const Text('Open settings'),
                    ),
                  ],
                ),
              Expanded(
                child: wide
                    ? Row(
                        children: [
                          NavigationRail(
                            selectedIndex: _index,
                            onDestinationSelected: (i) =>
                                setState(() => _index = i),
                            labelType: NavigationRailLabelType.all,
                            destinations: [
                              for (final t in tabs)
                                NavigationRailDestination(
                                  icon: Icon(t.icon),
                                  selectedIcon: Icon(t.selectedIcon),
                                  label: Text(t.label),
                                ),
                            ],
                          ),
                          const VerticalDivider(width: 1),
                          Expanded(child: tabs[_index].page),
                        ],
                      )
                    : Column(
                        children: [
                          Expanded(child: tabs[_index].page),
                          NavigationBar(
                            selectedIndex: _index,
                            onDestinationSelected: (i) =>
                                setState(() => _index = i),
                            destinations: [
                              for (final t in tabs)
                                NavigationDestination(
                                  icon: Icon(t.icon),
                                  selectedIcon: Icon(t.selectedIcon),
                                  label: t.label,
                                ),
                            ],
                          ),
                        ],
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}
