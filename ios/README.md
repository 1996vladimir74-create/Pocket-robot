# Pocket Robot iOS companion — source code

This folder contains the SwiftUI/CoreBluetooth app source. It is not an App Store build and has not been compiled because an Xcode/macOS environment is unavailable.

## Required Xcode target settings
- iOS deployment target: 16.0 or later.
- Add `PocketRobotApp.swift` to a new iOS App target.
- Use the supplied `Info.plist` (or copy its keys into the target Info settings).
- Enable Background Modes: Bluetooth LE accessory support / Uses Bluetooth LE accessories and Background fetch.
- Set the bundle identifier to `com.pocketrobot.phone` or change `refreshID` and `BGTaskSchedulerPermittedIdentifiers` together.
- Add an Apple Developer signing team to install on a physical iPhone.

## Setup
1. Install Tailscale on the Android server phone and iPhone, sign both into the same private tailnet.
2. Start the Flask server on Android. Use its Tailscale IPv4 address as the server URL, for example `http://100.x.y.z:8080`.
3. Copy `PHONE_TOKEN` from the private Android `server/config.py` into the app.
4. Run the app, grant Bluetooth permission, and tap Connect.
5. Keep the ESP32 powered and BLE advertising. The iPhone app scans for the Pocket Robot GATT service.
6. Send a test message through the server web page. The app polls its independent queue, writes the text over BLE, and acknowledges it only after the BLE write succeeds.

## Important delivery limitation
Foreground polling runs every 12 seconds. iOS Background App Refresh is opportunistic: its schedule is controlled by iOS and is not a real-time polling guarantee. Core Bluetooth background mode and state restoration help maintain an established connection, but do not guarantee delivery after the app is force-quit, the phone reboots, Bluetooth is disabled, or iOS suspends background work. This must be tested on the actual iPhone 14 Pro / iOS 26.4.

For reliable event-driven wake-up, a later release should add APNs push notifications. That requires an Apple Developer team, APNs key, server-side push provider configuration, and real-device testing. Do not treat this source-only build as a verified always-on service.

## Network security
The example uses HTTP to a Tailscale private address; traffic is carried inside the encrypted tailnet. Do not expose this server port to the public internet. The PHONE_TOKEN is a secret; do not put it in screenshots or commit a real token.
