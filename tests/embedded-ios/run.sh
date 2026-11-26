#!/bin/bash
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
app="$RUNNER_TEMP/GameWebView.app"
mkdir -p "$app" safari-evidence
cp "$here/route.js" "$app/"
python3 - "$app" <<'PY'
import pathlib,plistlib,sys
info=dict(CFBundleIdentifier="test.local.GameWebView",CFBundleName="GameWebView",CFBundleExecutable="GameWebView",CFBundlePackageType="APPL",CFBundleVersion="1",CFBundleShortVersionString="1.0",LSRequiresIPhoneOS=True,UILaunchScreen={},UIDeviceFamily=[1],CFBundleSupportedPlatforms=["iPhoneSimulator"],MinimumOSVersion="16.0")
(pathlib.Path(sys.argv[1])/"Info.plist").write_bytes(plistlib.dumps(info))
PY
xcrun --sdk iphonesimulator swiftc -target "$(uname -m)-apple-ios16.0-simulator" -sdk "$(xcrun --sdk iphonesimulator --show-sdk-path)" "$here/main.swift" -o "$app/GameWebView"
codesign --force --sign - "$app"
xcrun simctl install "$SIM_UDID" "$app"
bundle=test.local.GameWebView
data="$(xcrun simctl get_app_container "$SIM_UDID" "$bundle" data)"
failed=0
for game in garden mountain; do
  xcrun simctl launch --terminate-running-process "$SIM_UDID" "$bundle" "$game"
  result="$data/Documents/$game.txt"
  for ((n=0; n<100; n++)); do
    [[ -s "$result" ]] && break
    sleep 2
  done
  if [[ -f "$result" && "$(cat "$result")" == "ready" ]]; then
    xcrun simctl launch "$SIM_UDID" com.apple.Preferences
    sleep 3
    xcrun simctl launch "$SIM_UDID" "$bundle" "$game"
    for ((n=0; n<20; n++)); do
      [[ "$(cat "$result")" != "ready" ]] && break
      sleep 1
    done
  fi
  xcrun simctl io "$SIM_UDID" screenshot "safari-evidence/embedded-$game.png"
  if [[ -f "$result" ]]; then cp "$result" "safari-evidence/embedded-$game.txt"; cat "$result"; fi
  if [[ ! -f "$result" || "$(cat "$result")" != "PASS" ]]; then failed=1; fi
done
exit "$failed"
