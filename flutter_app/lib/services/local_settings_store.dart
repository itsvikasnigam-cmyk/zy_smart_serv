import 'dart:convert';
import 'dart:io';

/// Persists API base URL without `shared_preferences` (avoids Windows native
/// plugin symlink requirements for `flutter run -d windows`).
///
/// Data directory: `%APPDATA%\zy_smart_flutter\` on Windows, temp on Android.
class LocalSettingsStore {
  static Future<File> _settingsFile() async {
    if (Platform.isWindows) {
      final base = Platform.environment['APPDATA'];
      if (base != null && base.isNotEmpty) {
        final dir = Directory('$base${Platform.pathSeparator}zy_smart_flutter');
        if (!await dir.exists()) {
          await dir.create(recursive: true);
        }
        return File('${dir.path}${Platform.pathSeparator}settings.json');
      }
    } else if (Platform.isLinux) {
      final xdg = Platform.environment['XDG_CONFIG_HOME'];
      final home = Platform.environment['HOME'];
      final root = (xdg != null && xdg.isNotEmpty)
          ? '$xdg${Platform.pathSeparator}zy_smart_flutter'
          : '${home ?? '.'}${Platform.pathSeparator}.config${Platform.pathSeparator}zy_smart_flutter';
      final dir = Directory(root);
      if (!await dir.exists()) {
        await dir.create(recursive: true);
      }
      return File('${dir.path}${Platform.pathSeparator}settings.json');
    } else if (Platform.isMacOS) {
      final home = Platform.environment['HOME'] ?? '.';
      final dir = Directory(
        '$home${Platform.pathSeparator}Library${Platform.pathSeparator}Application Support${Platform.pathSeparator}zy_smart_flutter',
      );
      if (!await dir.exists()) {
        await dir.create(recursive: true);
      }
      return File('${dir.path}${Platform.pathSeparator}settings.json');
    }

    final tmp = Directory.systemTemp;
    return File(
      '${tmp.path}${Platform.pathSeparator}zy_smart_flutter_settings.json',
    );
  }

  static Future<Map<String, String>> readAll() async {
    try {
      final f = await _settingsFile();
      if (!await f.exists()) {
        return {};
      }
      final raw = await f.readAsString();
      if (raw.trim().isEmpty) {
        return {};
      }
      final decoded = jsonDecode(raw);
      if (decoded is! Map) {
        return {};
      }
      return decoded.map(
        (k, v) => MapEntry(k.toString(), v?.toString() ?? ''),
      );
    } catch (_) {
      return {};
    }
  }

  static Future<void> writeAll(Map<String, String> values) async {
    final f = await _settingsFile();
    await f.parent.create(recursive: true);
    const encoder = JsonEncoder.withIndent('  ');
    await f.writeAsString(encoder.convert(values));
  }
}
