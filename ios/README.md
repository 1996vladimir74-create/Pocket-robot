# Pocket Robot iPhone companion — source code

The iPhone 14 Pro app is a BLE relay between the permanent home Android server and the portable ESP32-S3 robot. This folder contains SwiftUI/CoreBluetooth source only. It is not a compiled installable app; building and signing requires Xcode on macOS.

## Fixed role

- Android server phone stays at home on home Wi-Fi.
- Pixel 9 sends messages to the spouse through the existing VK private chat.
- The home server watches only that configured dialog and sender ID.
- The iPhone app reaches the home server over Tailscale and forwards a fixed `NEW_MESSAGE` event to the robot over BLE when the ESP32 is not recently online.
- The app does not read VK, access message text, or relay the content of the conversation.
- The robot displays an envelope until MODE is pressed.

## Build and setup

1. Create a new iOS App target in Xcode, deployment target iOS 16.0 or later.
2. Add `PocketRobotApp.swift` to the target and use the supplied `Info.plist` keys.
3. Enable Background Modes for Bluetooth LE accessory support and Background fetch.
4. Set bundle identifier to `com.pocketrobot.phone`, or update the refresh task identifier in both source and Info.plist.
5. Add an Apple Developer signing team and install on iPhone 14 Pro.
6. Install Tailscale on the home Android server phone and iPhone; sign both into the same private tailnet.
7. Enter the Android phone's Tailscale IPv4 URL, e.g. `http://100.x.y.z:8080`, and the private `PHONE_TOKEN`.
8. Enable Bluetooth, open the app and connect to Pocket Robot.

## Relay behavior

Before taking an item from the phone queue, the app checks `/api/status`. If the ESP32 has polled the server recently, the app does not relay the same event over BLE. If the robot is offline, the app leases the phone-queue event, sends only the fixed `NEW_MESSAGE` marker in BLE chunks, and acknowledges the server queue after all BLE writes complete.

## Background limitation

Foreground polling runs approximately every 12 seconds. iOS Background App Refresh is opportunistic and is not a real-time polling guarantee. Core Bluetooth background mode and state restoration help maintain an established connection but do not guarantee delivery after force-quit, reboot, Bluetooth disablement or suspension. This must be tested on the actual iPhone 14 Pro / iOS 26.4.

A future APNs implementation could provide event-driven wake-up, but requires Apple Developer credentials, an APNs key, server-side push configuration and real-device testing. It is not included in this version.

## Network security

The example uses HTTP to a Tailscale private address; traffic is carried inside the encrypted tailnet. Do not expose port 8080 directly to the public internet. The `PHONE_TOKEN` is secret and must not be committed or shown in screenshots.
