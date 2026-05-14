import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';
import 'client_dashboard_screen.dart';
import 'inbox_chats_screen.dart';
import 'settings_screen.dart';
import 'super_admin_api_settings_sheet.dart';
import 'super_admin_shell.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, this.initialTab = 0});

  final int initialTab;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

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

class _HomeShellState extends State<HomeShell> {
  late int _index;

  @override
  void initState() {
    super.initState();
    _index = widget.initialTab;
  }

  List<_TabSpec> _tabsFor(SessionController session) {
    return [
      _TabSpec(
        icon: Icons.inbox_outlined,
        selectedIcon: Icons.inbox,
        label: 'Inbox',
        page: const InboxChatsScreen(),
      ),
      _TabSpec(
        icon: Icons.insights_outlined,
        selectedIcon: Icons.insights,
        label: 'Dashboard',
        page: ClientDashboardScreen(key: ValueKey(session.dashGeneration)),
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
    if (t.label == 'Dashboard') return 'Dashboard';
    return t.label;
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final user = session.user!;
    if (user.isSuperAdmin) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Super admin'),
          actions: [
            IconButton(
              tooltip: 'API base URLs',
              onPressed: () => showSuperAdminApiSettingsSheet(context),
              icon: const Icon(Icons.link),
            ),
            IconButton(
              tooltip: 'Log out',
              onPressed: session.logout,
              icon: const Icon(Icons.logout),
            ),
          ],
        ),
        body: const SuperAdminShell(),
      );
    }

    final tabs = _tabsFor(session);
    _index = _index.clamp(0, tabs.length - 1);

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 840;
        return Scaffold(
          appBar: AppBar(
            title: Text(_title(tabs, user.role)),
            actions: [
              IconButton(
                tooltip: 'Refresh inbox & dashboard',
                onPressed: () {
                  session.bumpInboxGeneration();
                  session.bumpDashGeneration();
                },
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: wide
              ? Row(
                  children: [
                    NavigationRail(
                      selectedIndex: _index,
                      onDestinationSelected: (i) => setState(() => _index = i),
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
                      onDestinationSelected: (i) => setState(() => _index = i),
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
        );
      },
    );
  }
}
