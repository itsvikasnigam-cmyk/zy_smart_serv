import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session_controller.dart';
import 'account_screen.dart';
import 'client_dashboard_screen.dart';
import 'inbox_chats_screen.dart';
import 'inbox_notifications_screen.dart';
import 'super_admin_api_settings_sheet.dart';
import 'super_admin_shell.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final session = context.read<SessionController>();
      if (session.isLoggedIn && !session.user!.isSuperAdmin) {
        unawaited(session.refreshUnreadNotificationCount());
      }
    });
  }

  String _titleForIndex(int i, String role) {
    switch (i) {
      case 0:
        return 'Inbox · $role';
      case 1:
        return 'Alerts · $role';
      case 2:
        return 'Dashboard';
      default:
        return 'Account';
    }
  }

  Widget _badgeIcon(Widget icon, int count) {
    if (count <= 0) return icon;
    return Badge(
      label: Text(count > 99 ? '99+' : '$count'),
      child: icon,
    );
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

    final unread = session.unreadNotificationCount;
    final pages = <Widget>[
      const InboxChatsScreen(),
      const InboxNotificationsScreen(),
      ClientDashboardScreen(key: ValueKey(session.dashGeneration)),
      const AccountScreen(),
    ];
    _index = _index.clamp(0, pages.length - 1);

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 840;
        if (wide) {
          return Scaffold(
            appBar: AppBar(
              title: Text(_titleForIndex(_index, user.role)),
              actions: [
                IconButton(
                  tooltip: 'Refresh inbox, alerts & dashboard',
                  onPressed: () {
                    session.bumpInboxGeneration();
                    session.bumpNotificationsGeneration();
                    session.bumpDashGeneration();
                    unawaited(session.refreshUnreadNotificationCount());
                  },
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            body: Row(
              children: [
                NavigationRail(
                  selectedIndex: _index,
                  onDestinationSelected: (i) {
                    setState(() => _index = i);
                    if (i == 1) {
                      session.bumpNotificationsGeneration();
                      unawaited(session.refreshUnreadNotificationCount());
                    }
                  },
                  labelType: NavigationRailLabelType.all,
                  destinations: [
                    const NavigationRailDestination(
                      icon: Icon(Icons.inbox_outlined),
                      selectedIcon: Icon(Icons.inbox),
                      label: Text('Inbox'),
                    ),
                    NavigationRailDestination(
                      icon: _badgeIcon(
                        const Icon(Icons.notifications_outlined),
                        unread,
                      ),
                      selectedIcon: _badgeIcon(
                        const Icon(Icons.notifications),
                        unread,
                      ),
                      label: const Text('Alerts'),
                    ),
                    const NavigationRailDestination(
                      icon: Icon(Icons.insights_outlined),
                      selectedIcon: Icon(Icons.insights),
                      label: Text('Dashboard'),
                    ),
                    const NavigationRailDestination(
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
            title: Text(_titleForIndex(_index, user.role)),
            actions: [
              IconButton(
                tooltip: 'Refresh inbox, alerts & dashboard',
                onPressed: () {
                  session.bumpInboxGeneration();
                  session.bumpNotificationsGeneration();
                  session.bumpDashGeneration();
                  unawaited(session.refreshUnreadNotificationCount());
                },
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: pages[_index],
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (i) {
              setState(() => _index = i);
              if (i == 1) {
                session.bumpNotificationsGeneration();
                unawaited(session.refreshUnreadNotificationCount());
              }
            },
            destinations: [
              const NavigationDestination(
                icon: Icon(Icons.inbox_outlined),
                selectedIcon: Icon(Icons.inbox),
                label: 'Inbox',
              ),
              NavigationDestination(
                icon: _badgeIcon(
                  const Icon(Icons.notifications_outlined),
                  unread,
                ),
                selectedIcon: _badgeIcon(
                  const Icon(Icons.notifications),
                  unread,
                ),
                label: 'Alerts',
              ),
              const NavigationDestination(
                icon: Icon(Icons.insights_outlined),
                selectedIcon: Icon(Icons.insights),
                label: 'Dashboard',
              ),
              const NavigationDestination(
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
