# ZY Smart Serv — Flutter client (`mobile/`)

Cross-platform inbox UI for **client_api** (M3/M4): JWT login, role-based navigation (**owner** / **agent** / **super_admin**), inbox over REST + WebSocket, and a **super_admin** control-plane placeholder for future `ops_runtime_config` APIs.

## Prerequisites

- [Flutter SDK](https://docs.flutter.dev/get-started/install) (stable), with **Android** + **Windows** desktop enabled.
- Running `client_api` (default dev URL `http://127.0.0.1:8085`). See repo root `README.md` and `HANDOFF.md`.

Settings (API base URL, super_admin `client_id`) are persisted with a small JSON file via `lib/services/local_settings_store.dart` (no `shared_preferences`), so **Windows desktop builds avoid symlink/Developer Mode** unless you add other native plugins.

## First-time project setup (platform folders)

This directory ships with `lib/`, `pubspec.yaml`, and tests. Generate native runners once:

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window\mobile
flutter create . --project-name zy_smart_client --platforms=android,windows
flutter pub get
```

`flutter create .` adds `android/`, `windows/`, etc., without replacing your `lib/` code.

## Backend URL (dev)

| Target | Typical base URL |
|--------|-------------------|
| Windows desktop (same machine as API) | `http://127.0.0.1:8085` |
| Android **emulator** → host machine | `http://10.0.2.2:8085` |
| Physical device on LAN | `http://<your-pc-lan-ip>:8085` |

Configure in-app via **Connection settings** on the login screen or **Settings** after login (see `LocalSettingsStore` for file locations).

Build-time override:

```powershell
flutter run --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085
```

## `super_admin` tenant scope

REST calls require `?client_id=<uuid>` and the WebSocket requires `&client_id=` as well. In **Settings**, paste the tenant UUID and tap **Save client scope**, then toggle the WebSocket switch if needed.

## Run

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window\mobile
flutter pub get
flutter run -d windows
flutter run -d android
```

## Android cleartext (HTTP) for local dev

If you use `http://` against a non-HTTPS API, the release/debug manifest from `flutter create` may need cleartext allowed for dev. After `flutter create .`, add to `android/app/src/debug/AndroidManifest.xml` inside `<application>`:

```xml
<application android:usesCleartextTraffic="true" ...>
```

(Or use HTTPS / reverse proxy in staging.)

## Tests

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window\mobile
flutter test
```
