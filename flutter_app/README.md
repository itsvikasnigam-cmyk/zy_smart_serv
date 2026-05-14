# zy_smart_flutter

Flutter client shell for **client_api** (login, **owner/agent** inbox + WebSocket + **`GET /dash/client/*`** dashboard) and **super_admin** **SOP Runbook Center** against **`ops_api`** (`OPS_API_BASE_URL`, same JWT as login).

## Owner / agent (Chat G — inbox + client dashboard)

After sign-in as **`owner`** or **`agent`**, tabs are **Inbox** · **Dashboard** · **Account**. Inbox uses REST (`/inbox/*`) plus **`/ws`** for live updates. **Dashboard** calls read-only **`GET /dash/client/overview`**, **`.../agents`**, **`.../quality`** (Chat J). If those routes return **404**, the app shows an **offline preview** card so layouts stay usable until `client_api` is upgraded.

| Target | `CLIENT_API_BASE_URL` example |
|--------|-------------------------------|
| **Windows desktop** (same machine as `client_api`) | `http://127.0.0.1:8085` |
| **Android emulator** (host loopback) | `http://10.0.2.2:8085` |
| **Physical Android device** (LAN) | `http://<your-pc-lan-ip>:8085` |

Use **Connection settings** (or `--dart-define`) so the app matches where `uvicorn` is listening. WebSocket URL is derived from the same base (`ws` / `wss`), path `/ws?token=…`.

## Super admin — SOP / Runbook (`ops_api`)

Log in as **`super_admin`**. Use the **link** icon in the app bar to set **`CLIENT_API_BASE_URL`** (default `http://127.0.0.1:8085`) and **`OPS_API_BASE_URL`** (default `http://127.0.0.1:8087`). Tabs: **SOPs**, **Runs**, **Control** (read-only M8 placeholders), **Dash** (read-only `GET /dash/admin/*` on **client_api**).

**Auth errors**: **401** from `ops_api` → **logout**. **403** → one message (**super_admin** required); **no retry loop**.

**Flutter Web (dev CORS)**: set `CLIENT_API_CORS_ORIGINS` and `OPS_API_CORS_ORIGINS` to the **exact** browser origin (e.g. `http://localhost:5555` from `flutter run -d chrome`). Do not use `*` with `Authorization: Bearer`.

Build-time overrides:

```text
--dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085 --dart-define=OPS_API_BASE_URL=http://127.0.0.1:8087
```

## Fix: `No Windows desktop project configured`

This repo tracks Dart sources only until you materialize platform folders locally. From **`flutter_app`** (this directory), run **once**:

```powershell
flutter create . --project-name zy_smart_flutter --org com.zysmart.serv --platforms=windows
```

For Android as well (or both):

```powershell
flutter create . --project-name zy_smart_flutter --org com.zysmart.serv --platforms=android,windows
```

Then `flutter pub get` and `flutter run -d windows` again.

## Git paths (common mistake)

Git metadata lives in the **repo root** (`empty-window`), not inside `flutter_app/`.

| Your shell cwd | Stage `home_shell.dart` |
|----------------|-------------------------|
| `...\empty-window` (root) | `git add flutter_app/lib/screens/home_shell.dart` |
| `...\empty-window\flutter_app` | `git add lib/screens/home_shell.dart` |

Using `git add flutter_app/lib/...` **while cwd is `flutter_app`** doubles the path and fails.

**`pubspec.lock`:** after `flutter pub get`, consider committing it from the repo root: `git add flutter_app/pubspec.lock`.

## First-time setup (native platforms)

If `android/` or `windows/` is missing, generate them once from this directory:

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window\flutter_app
flutter create . --project-name zy_smart_flutter --org com.zysmart.serv --platforms=android,windows
```

Then:

```powershell
flutter pub get
```

## API base URL

- **Default:** `http://127.0.0.1:8085` (same as repo README for `client_api`).
- **Override at run time:** `--dart-define=CLIENT_API_BASE_URL=<url>`
- **Android emulator → host machine:** use `http://10.0.2.2:8085` (or the same dart-define).
- The app also persists the last URL from the **API base URL** screen (no `shared_preferences`; see `lib/services/local_settings_store.dart`).

## Run

Windows desktop:

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window\flutter_app
flutter run -d windows --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085 --dart-define=OPS_API_BASE_URL=http://127.0.0.1:8087
```

Android (emulator or device):

```powershell
flutter devices
flutter run -d <deviceId> --dart-define=CLIENT_API_BASE_URL=http://10.0.2.2:8085 --dart-define=OPS_API_BASE_URL=http://10.0.2.2:8087
```

WebSocket URL is derived from the same base (http→ws, https→wss), path `/ws?token=<JWT>` per README.

## Tests

```powershell
flutter test
```
