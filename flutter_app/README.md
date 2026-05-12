# zy_smart_flutter

Flutter client shell for **client_api** (login, owner/agent inbox + WebSocket, super_admin control-plane placeholder).

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
flutter run -d windows --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085
```

Android (emulator or device):

```powershell
flutter devices
flutter run -d <deviceId> --dart-define=CLIENT_API_BASE_URL=http://10.0.2.2:8085
```

WebSocket URL is derived from the same base (http→ws, https→wss), path `/ws?token=<JWT>` per README.

## Tests

```powershell
flutter test
```
