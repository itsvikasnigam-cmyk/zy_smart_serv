import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';
import 'account_screen.dart';
import 'inbox_chats_screen.dart';
import 'super_admin_control_plane_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionController>();
    final user = session.user!;
    if (user.isSuperAdmin) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Control plane'),
          actions: [
            IconButton(
              tooltip: 'Log out',
              onPressed: session.logout,
              icon: const Icon(Icons.logout),
            ),
          ],
        ),
        body: const SuperAdminControlPlaneScreen(),
      );
    }

    final pages = const [
      InboxChatsScreen(),
      AccountScreen(),
    ];
    _index = _index.clamp(0, pages.length - 1);

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 840;
        if (wide) {
          return Scaffold(
            appBar: AppBar(
              title: Text(_index == 0 ? 'Inbox · ${user.role}' : 'Account'),
              actions: [
                IconButton(
                  tooltip: 'Refresh inbox',
                  onPressed: session.bumpInboxGeneration,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            body: Row(
              children: [
                NavigationRail(
                  selectedIndex: _index,
                  onDestinationSelected: (i) => setState(() => _index = i),
                  labelType: NavigationRailLabelType.all,
                  destinations: const [
                    NavigationRailDestination(
                      icon: Icon(Icons.inbox_outlined),
                      selectedIcon: Icon(Icons.inbox),
                      label: Text('Inbox'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.person_outline),
                      selectedIcon: Icon(Icons.person),
                      label: Text('Account'),
                    ),
                  ],
                ),
                const VerticalDivider(width: 1),
                Expanded(child: pages[_index]),
              ],
            ),
          );
        }
        return Scaffold(
          appBar: AppBar(
            title: Text(_index == 0 ? 'Inbox · ${user.role}' : 'Account'),
            actions: [
              IconButton(
                tooltip: 'Refresh inbox',
                onPressed: session.bumpInboxGeneration,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: pages[_index],
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.inbox_outlined),
                selectedIcon: Icon(Icons.inbox),
                label: 'Inbox',
              ),
              NavigationDestination(
                icon: Icon(Icons.person_outline),
                selectedIcon: Icon(Icons.person),
                label: 'Account',
              ),
            ],
          ),
        );
      },
    );
  }
}
