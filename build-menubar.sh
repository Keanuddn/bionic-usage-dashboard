#!/usr/bin/env bash
# Builds BionicLimit.app — a native menu bar item showing the remaining
# Bionic+ weekly limit. Requires Xcode command line tools (swiftc).
#
# Usage:  BIONIC_DASHBOARD_PATH="$PWD" ./build-menubar.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Applications/BionicLimit.app"

mkdir -p "$APP/Contents/MacOS"
swiftc -O "$HERE/BionicLimit.swift" -o "$APP/Contents/MacOS/BionicLimit"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>com.bioniclimit.app</string>
  <key>CFBundleName</key><string>BionicLimit</string>
  <key>CFBundleExecutable</key><string>BionicLimit</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
EOF

# LaunchAgent: autostart + KeepAlive
PLIST="$HOME/Library/LaunchAgents/com.bioniclimit.app.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.bioniclimit.app</string>
  <key>ProgramArguments</key>
  <array>
    <string>$APP/Contents/MacOS/BionicLimit</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>BIONIC_DASHBOARD_PATH</key><string>$HERE</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
pkill -f BionicLimit 2>/dev/null || true
launchctl load "$PLIST"
echo "BionicLimit installed and running — check your menu bar."
