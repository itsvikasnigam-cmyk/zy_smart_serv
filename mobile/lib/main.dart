import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'state/session_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final session = SessionController();
  await session.loadPersistedSettings();
  runApp(
    ChangeNotifierProvider<SessionController>.value(
      value: session,
      child: const ZySmartClientApp(),
    ),
  );
}

class ZySmartClientApp extends StatelessWidget {
  const ZySmartClientApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ZY Smart Serv',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0D9488)),
        useMaterial3: true,
      ),
      home: Consumer<SessionController>(
        builder: (context, session, _) {
          return session.isLoggedIn ? const HomeShell() : const LoginScreen();
        },
      ),
    );
  }
}
