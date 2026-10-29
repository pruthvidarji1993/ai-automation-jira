# Mobile and desktop shell checklist (Capacitor, Electron, React Native)

## Capacitor

- `capacitor.config.*` `server.url` pointing at a remote or `http://` host in a
  production build; `server.cleartext: true`; `android:usesCleartextTraffic`.
- `server.allowNavigation` with wildcards (`*`, `*.com`) - any matching page
  gets the native bridge.
- Tokens or personal data in `@capacitor/preferences` or `localStorage`
  (plain files on device) instead of Keychain/Keystore-backed storage.
- Deep links / custom URL schemes / App Links whose handler navigates, logs in
  or performs actions from URL parameters without validation; missing
  `assetlinks.json` / `apple-app-site-association` verification.
- Custom native plugins exposing file system, shell, contacts or auth tokens to
  any JS running in the WebView without checking the caller.
- `WebView.setWebContentsDebuggingEnabled(true)` or `isInspectable = true` in
  release builds; `android:debuggable` or `allowBackup="true"` with sensitive data.
- Exported Android components (activities, receivers, providers) without
  permissions; overly broad `Info.plist` / manifest permissions.
- Push notification payloads carrying sensitive data shown on the lock screen.

## Electron

- `nodeIntegration: true`, `contextIsolation: false`, `sandbox: false`, or
  `webSecurity: false` on any window that loads remote or user content.
- `preload` exposing raw `ipcRenderer`, `require`, `fs` or `child_process`
  through `contextBridge` instead of narrow, validated functions.
- `ipcMain.handle` handlers that trust arguments (paths, URLs, commands) from
  the renderer without validation.
- `shell.openExternal(url)` with unvalidated URLs (can launch `file:` or
  custom-protocol handlers).
- No `will-navigate` / `setWindowOpenHandler` restriction - a link can load a
  remote page into a privileged window.
- Auto-update over HTTP or without signature verification; custom protocol
  handlers allowing path traversal.
- Missing CSP on locally loaded pages.

## React Native

- Secrets embedded in the JS bundle or `.env` compiled into the app (the
  bundle is readable).
- Tokens in `AsyncStorage` instead of Keychain/Keystore (e.g. a secure-store
  library).
- `WebView` with `originWhitelist={['*']}`, `javaScriptEnabled` on untrusted
  content, or `onMessage` handlers trusting any page.
- Deep link handlers performing actions from URL parameters.
- Certificate pinning absent for high-value APIs (note-only unless required).

## Native iOS side (ios/ in Capacitor and React Native apps)

- Tokens in `UserDefaults` instead of Keychain; secrets in `Info.plist`.
- `NSAllowsArbitraryLoads` in App Transport Security.
- `WKWebView` message handlers exposed to remote pages; universal link / URL
  scheme handlers acting on parameters without validation.
- Sensitive screens not hidden in the app-switcher snapshot.
