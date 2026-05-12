import 'dart:convert';
import 'dart:io';

/// Persists a few strings without `shared_preferences` (no Windows native plugin →
/// no symlink requirement for `flutter run -d windows`).
///
/// - **Windows:** `%APPDATA%\zy_smart_client\settings.json`
/// - **Linux:** `$XDG_CONFIG_HOME/zy_smart_client/settings.json` or `~/.config/...`
/// - **macOS:** `~/Library/Application Support/zy_smart_client/settings.json`
/// - **Android / iOS / other:** `Directory.systemTemp` (app cache/temp; fine for dev URLs).
class LocalSettingsStore {
  static Future<File> _settingsFile() async {
    if (Platform.isWindows) {
      final base = Platform.environment['APPDATA'];
      if (base != null && base.isNotEmpty) {
        final dir = Directory('$base${Platform.pathSeparator}zy_smart_client');
        if (!await dir.exists()) {
          await dir.create(recursive: true);
        }
        return File('${dir.path}${Platform.pathSeparator}settings.json');
      }
    } else if (Platform.isLinux) {
      final xdg = Platform.environment['XDG_CONFIG_HOME'];
      final home = Platform.environment['HOME'];
      final root = (xdg != null && xdg.isNotEmpty)
          ? '$xdg${Platform.pathSeparator}zy_smart_client'
          : '${home ?? '.'}${Platform.pathSeparator}.config${Platform.pathSeparator}zy_smart_client';
      final dir = Directory(root);
      if (!await dir.exists()) {
        await dir.create(recursive: true);
      }
      return File('${dir.path}${Platform.pathSeparator}settings.json');
    } else if (Platform.isMacOS) {
      final home = Platform.environment['HOME'] ?? '.';
      final dir = Directory(
        '$home${Platform.pathSeparator}Library${Platform.pathSeparator}Application Support${Platform.pathSeparator}zy_smart_client',
      );
      if (!await dir.exists()) {
        await dir.create(recursive: true);
      }
      return File('${dir.path}${Platform.pathSeparator}settings.json');
    }

    final tmp = Directory.systemTemp;
    return File(
      '${tmp.path}${Platform.pathSeparator}zy_smart_client_settings.json',
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
