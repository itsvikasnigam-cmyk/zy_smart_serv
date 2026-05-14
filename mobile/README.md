# ZY Smart Serv — Flutter client (`mobile/`)

Cross-platform UI for **client_api** (M3/M4): JWT login, **owner** / **agent** inbox over REST + WebSocket, **read-only client dashboard** (`GET /dash/client/*`, Chat J), and **super_admin** **SOP / Runbook Center** against **`ops_api`** (same JWT) — mirrors `flutter_app/` (Chat H).

## Owner / agent (Chat G)

Tabs: **Inbox** · **Dashboard** · **Settings**. **Dashboard** loads overview, agents, and quality from **`/dash/client/*`**. If those routes are missing (**404**), the UI shows an **offline preview** so shells stay testable. **Super admin** scoped inbox: set **client UUID** under **Settings** before opening **Inbox**.

## Prerequisites

- [Flutter SDK](https://docs.flutter.dev/get-started/install) (stable), with **Android** + **Windows** desktop enabled.
- Running **`client_api`** (default `http://127.0.0.1:8085`) and **`ops_api`** (default `http://127.0.0.1:8087`) for super-admin SOP flows. See repo root `README.md`.

Settings (API base URLs) are persisted with a small JSON file via `lib/services/local_settings_store.dart` (no `shared_preferences`), so **Windows desktop builds avoid symlink/Developer Mode** unless you add other native plugins.

## First-time project setup (platform folders)

This directory ships with `lib/`, `pubspec.yaml`, and tests. Generate native runners once:

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window\mobile
flutter create . --project-name zy_smart_client --platforms=android,windows
flutter pub get
```

`flutter create .` adds `android/`, `windows/`, etc., without replacing your `lib/` code.

## Backend URLs (dev)

| App | Env / define | Default | Android emulator → host |
|-----|----------------|---------|---------------------------|
| **client_api** | `CLIENT_API_BASE_URL` | `http://127.0.0.1:8085` | `http://10.0.2.2:8085` |
| **ops_api** | `OPS_API_BASE_URL` | `http://127.0.0.1:8087` | `http://10.0.2.2:8087` |

Configure **both** in-app after **super_admin** login via the app bar **link** icon (same as `flutter_app`), or use dart-define:

```powershell
flutter run -d windows --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085 --dart-define=OPS_API_BASE_URL=http://127.0.0.1:8087
```

**Flutter Web (dev CORS):** set `CLIENT_API_CORS_ORIGINS` and `OPS_API_CORS_ORIGINS` on the servers to the **exact** browser origin (e.g. `http://localhost:5555`). Do not use `*` with `Authorization: Bearer`.

## Super admin

After login as **super_admin**, the app shows the **Super admin** shell: **SOPs**, **Runs**, **Control** (read-only M8 placeholders), **Dash** (`GET /dash/admin/*` on **client_api**). **401** from either API logs you out; **403** from `ops_api` shows a one-shot **needs super_admin** message (no retry loop).

## Run

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window\mobile
flutter pub get
flutter run -d windows --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085 --dart-define=OPS_API_BASE_URL=http://127.0.0.1:8087
flutter run -d android --dart-define=CLIENT_API_BASE_URL=http://10.0.2.2:8085 --dart-define=OPS_API_BASE_URL=http://10.0.2.2:8087
```

Non–super-admin users: **Connection settings** on the login screen or **Settings → API base URL** for **client_api** only; WebSocket connects after login for **owner** / **agent**. If you ever passed `HomeShell(initialTab: …)`, note tab order is **0=Inbox, 1=Dashboard, 2=Settings** (Settings was previously index `1` before the dashboard tab existed).

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
