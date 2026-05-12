import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:zy_smart_flutter/main.dart';
import 'package:zy_smart_flutter/state/session_controller.dart';

void main() {
  testWidgets('Sign in screen renders', (tester) async {
    final session = SessionController();
    await session.loadPersistedSettings();
    await tester.pumpWidget(
      ChangeNotifierProvider<SessionController>.value(
        value: session,
        child: const ZySmartFlutterApp(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Sign in'), findsOneWidget);
  });
}
