# Pocket Robot V1 — release and assembly plan

**Software/integration target:** 20 November 2026  
**Physical enclosure assembly:** 22 November 2026

## Locked behavior

- The Android server phone remains at home, powered and connected to home Wi-Fi.
- Pixel 9 sends an ordinary message to the spouse through the existing private VK chat.
- The home server checks only the configured VK dialog and the configured sender ID.
- VK text and attachments are not copied to the robot. The only payload is the fixed `NEW_MESSAGE` event.
- At home, ESP32-S3 receives the event directly over home Wi-Fi.
- Away from home, iPhone 14 Pro receives the event from the home server over Tailscale and relays it to ESP32-S3 over BLE.
- The robot shows an envelope icon until MODE is pressed.
- A separate web sender is deferred to the next development stage.

## Test sequence

### 1. Home server — 16 November
- [ ] Clone `feature/vk-envelope-notifications` on the permanent Android server phone.
- [ ] Install dependencies in Termux and create private `server/config.py`.
- [ ] Set unique ADMIN, DEVICE and PHONE tokens.
- [ ] Start Flask and confirm `/health` from another device on home Wi-Fi.
- [ ] Enable Termux wake lock and review Android battery restrictions.

### 2. VK integration — 16–17 November
- [ ] Configure the VK token, private-dialog peer ID and Pixel 9 owner's VK user ID.
- [ ] Confirm first poll establishes a baseline without replaying old messages.
- [ ] Send a new VK message from Pixel 9 to the spouse's configured chat.
- [ ] Confirm the server emits one `NEW_MESSAGE` event.
- [ ] Confirm a message from another sender or another dialog does not trigger the robot.
- [ ] Confirm message text and attachments are not forwarded or stored by the VK watcher.

### 3. Robot on home Wi-Fi — 17–18 November
- [ ] Configure ESP32 home Wi-Fi and the Android server's home-LAN address.
- [ ] Flash/test the updated MicroPython firmware.
- [ ] Confirm ESP32 presence becomes online in `/api/status`.
- [ ] Send a VK message and confirm the envelope appears.
- [ ] Press MODE and confirm the envelope disappears.
- [ ] Confirm the same event is not also relayed by the iPhone BLE queue while the robot is online.

### 4. iPhone BLE relay — 18–19 November
- [ ] Build and sign the SwiftUI source on a Mac with Xcode.
- [ ] Install on iPhone 14 Pro / iOS 26.4 and grant Bluetooth permissions.
- [ ] Join the iPhone and home Android server phone to the same Tailscale network.
- [ ] Configure server Tailscale URL and PHONE_TOKEN in the iOS app.
- [ ] Turn off robot Wi-Fi or move it out of home coverage.
- [ ] Confirm the iPhone app sees the robot as offline, receives the queue event and writes `NEW_MESSAGE` over BLE.
- [ ] Confirm the envelope appears and MODE clears it.
- [ ] Test with the iOS app foregrounded first; then test background behavior separately.

### 5. Integration freeze — by 20 November
- [ ] Repeat the home Wi-Fi notification test.
- [ ] Repeat the away-from-home BLE relay test.
- [ ] Check that repeated polling does not create duplicate notifications.
- [ ] Check that a failed BLE write does not acknowledge the server queue.
- [ ] Record unresolved issues and freeze the V1 software branch.

## Hotspot direct mode — not part of the verified first test

ESP32 connected to iPhone Personal Hotspot has internet access, but it cannot directly use the Android phone's Tailscale IP because the ESP32 is not a Tailscale node. Direct mode needs a secure public HTTPS endpoint for the home server and a verified TLS-capable MicroPython client. Do not expose the Flask port directly to the public internet. Until this path is implemented and tested, use the iPhone BLE relay away from home.

## Physical enclosure — 22 November

- [ ] Confirm the firmware and electronics pass the software/integration checks before closing the enclosure.
- [ ] Check display orientation, button access, USB-C access, power switch and ventilation.
- [ ] Confirm wiring is secured and does not interfere with the display or enclosure panels.
- [ ] Run a final power-on, Wi-Fi and notification check after assembly.

## Known external dependency

The iOS companion in this repository is source code only. It has not been compiled or installed because a macOS/Xcode environment is not available in the current development setup. A Mac with Xcode and Apple signing access is required to complete the physical iPhone relay test. iOS background polling is opportunistic; foreground operation must be verified first.
