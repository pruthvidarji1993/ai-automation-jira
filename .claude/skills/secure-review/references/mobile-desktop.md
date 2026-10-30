# Mobile checklist (React Native, native iOS)

## React Native

- Secrets embedded in the JS bundle or `.env` compiled into the app (the
  bundle is readable).
- Tokens in `AsyncStorage` instead of Keychain/Keystore (e.g. a secure-store
  library).
- `WebView` with `originWhitelist={['*']}`, `javaScriptEnabled` on untrusted
  content, or `onMessage` handlers trusting any page.
- Deep link handlers performing actions from URL parameters.
- Certificate pinning absent for high-value APIs (note-only unless required).

## Native iOS side (ios/ in React Native apps)

- Tokens in `UserDefaults` instead of Keychain; secrets in `Info.plist`.
- `NSAllowsArbitraryLoads` in App Transport Security.
- `WKWebView` message handlers exposed to remote pages; universal link / URL
  scheme handlers acting on parameters without validation.
- Sensitive screens not hidden in the app-switcher snapshot.
