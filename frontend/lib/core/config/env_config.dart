import 'package:flutter/foundation.dart';

class EnvConfig {
  static const String appName = 'Schemora';
  static const String appVersion = '1.0.0';

  // Development Port
  static const String devPort = '8000';

  // ─────────────────────────────────────────────────────────────────────────
  // ANDROID TARGET HOST SELECTION
  //
  // ✅ ALWAYS use the dev runner script — it auto-detects your current IP:
  //      .\run_dev.ps1                  (physical phone, auto IP)
  //      .\run_dev.ps1 -Emulator        (Android emulator)
  //      .\run_dev.ps1 -d <device-id>   (specific device)
  //
  // Or pass manually:
  //      flutter run --dart-define=DEV_HOST_IP=<YOUR_PC_LAN_IP>
  //
  // ⚠️  NEVER hardcode the IP here — it changes every time you switch networks.
  // ─────────────────────────────────────────────────────────────────────────

  /// LAN IP of the dev machine — injected at build time by run_dev.ps1.
  /// Defaults to 10.59.33.142.
  static const String devHostIp =
      String.fromEnvironment('DEV_HOST_IP', defaultValue: '10.59.33.142');

  // Set to 'true' only when running on Android Emulator
  static const bool _useEmulator =
      String.fromEnvironment('USE_EMULATOR', defaultValue: 'false') == 'true';

  // Production or custom URL override via --dart-define=API_BASE_URL=https://...
  static const String _overrideBaseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: '');

  /// Deterministic API base URL:
  /// - Production:      --dart-define=API_BASE_URL=https://...
  /// - Android Emulator: http://10.0.2.2:8000/api/v1/
  /// - Web / Desktop:    http://127.0.0.1:8000/api/v1/
  static String get baseUrl {
    if (_overrideBaseUrl.isNotEmpty) {
      final raw = _overrideBaseUrl;
      return raw.endsWith('/') ? raw : '$raw/';
    }

    String host;
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      // 10.0.2.2 maps directly to host PC localhost on Android Emulator (<1ms)
      host = '10.0.2.2';
    } else {
      host = '127.0.0.1';
    }

    return 'http://$host:$devPort/api/v1/';
  }

  // Fast, crisp timeout settings (5s connect, 30s receive, 15s send)
  static const int connectTimeoutMs = 5000;
  static const int receiveTimeoutMs = 30000;
  static const int sendTimeoutMs = 15000;
}
