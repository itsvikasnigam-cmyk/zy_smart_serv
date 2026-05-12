import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:zy_smart_client/main.dart';
import 'package:zy_smart_client/state/session_controller.dart';

void main() {
  testWidgets('Login screen builds', (tester) async {
    final session = SessionController();
    await session.loadPersistedSettings();
    await tester.pumpWidget(
      ChangeNotifierProvider<SessionController>.value(
        value: session,
        child: const ZySmartClientApp(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Sign in'), findsOneWidget);
  });
}
