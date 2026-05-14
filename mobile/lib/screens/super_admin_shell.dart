import 'package:flutter/material.dart';

import 'sops/sop_library_screen.dart';
import 'sops/sop_runs_list_screen.dart';
import 'super_admin_control_plane_screen.dart';
import 'super_admin_dash_screen.dart';

/// Super-admin: SOP Center, run logs, read-only control plane, Chat J dashboards.
class SuperAdminShell extends StatefulWidget {
  const SuperAdminShell({super.key});

  @override
  State<SuperAdminShell> createState() => _SuperAdminShellState();
}

class _SuperAdminShellState extends State<SuperAdminShell> {
  int _tab = 0;
  final _sopNavKey = GlobalKey<NavigatorState>();
  final _runsNavKey = GlobalKey<NavigatorState>();

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        final nav = _tab == 0
            ? _sopNavKey.currentState
            : _tab == 1
                ? _runsNavKey.currentState
                : null;
        if (nav != null && nav.canPop()) {
          nav.pop();
        } else if (_tab != 0) {
          setState(() => _tab = 0);
        }
      },
      child: Scaffold(
        body: IndexedStack(
          index: _tab,
          children: [
            Navigator(
              key: _sopNavKey,
              home: const SopLibraryScreen(),
            ),
            Navigator(
              key: _runsNavKey,
              home: const SopRunsListScreen(),
            ),
            const SuperAdminControlPlaneScreen(),
            const SuperAdminDashScreen(),
          ],
        ),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) => setState(() => _tab = i),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.menu_book_outlined),
              selectedIcon: Icon(Icons.menu_book),
              label: 'SOPs',
            ),
            NavigationDestination(
              icon: Icon(Icons.receipt_long_outlined),
              selectedIcon: Icon(Icons.receipt_long),
              label: 'Runs',
            ),
            NavigationDestination(
              icon: Icon(Icons.tune_outlined),
              selectedIcon: Icon(Icons.tune),
              label: 'Control',
            ),
            NavigationDestination(
              icon: Icon(Icons.insights_outlined),
              selectedIcon: Icon(Icons.insights),
              label: 'Dash',
            ),
          ],
        ),
      ),
    );
  }
}
