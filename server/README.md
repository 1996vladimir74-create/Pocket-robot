# Pocket Robot — home server, VK event and iPhone BLE relay

## Fixed architecture for this release

- **Home server:** a dedicated Android smartphone stays at home and remains connected to the home Wi-Fi. Termux runs Flask, SQLite and the VK watcher.
- **Sender:** Pixel 9 sends an ordinary message to the spouse in their existing private VK chat. No separate website or app is required for the primary workflow.
- **VK filter:** the server checks only the configured private-dialog `peer_id` and accepts only messages whose `from_id` is the Pixel 9 owner's VK account ID.
- **Robot at home:** ESP32-S3 connects to home Wi-Fi and polls the home server directly.
- **Robot away — BLE mode:** iPhone 14 Pro connects to the home server over Tailscale, receives the event and forwards the fixed `NEW_MESSAGE` marker to ESP32 over BLE.
- **Robot away — hotspot mode:** the ESP32 can use iPhone Personal Hotspot for internet access only after a secure public HTTPS endpoint for the home server is configured. A plain ESP32 device cannot reach a Tailscale-only IP. Direct HTTPS transport from MicroPython is not enabled in this release; use BLE mode for the first tests.

The server never forwards VK message text or attachments. It emits only a content-free notification event. The robot displays an envelope icon until MODE is pressed. It does not determine whether the VK message was read.

## Delivery selection and duplicate prevention

The ESP32 updates its server presence whenever it polls `/api/robot/messages/next`. The server reports the robot online for 45 seconds after the last poll. The iPhone app checks `/api/status` before reading its BLE queue:
- if the robot is online, the iPhone does not relay the event;
- if the robot is offline, the iPhone reads the phone queue and sends the event over BLE.

This prevents the normal home-Wi-Fi and BLE paths from displaying the same notification twice. When the robot moves away, the server waits for its presence lease to expire before the iPhone app starts relaying.

## Termux setup on the permanent home server phone

1. Install Termux and Python.
2. Clone branch `feature/vk-envelope-notifications`.
3. `cd server && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
4. `cp config.example.py config.py`; set three unique long tokens and the weather coordinates for home.
5. Keep `VK_ENABLED=False` until the VK token and IDs are configured.
6. During testing run `termux-wake-lock` and exclude Termux from Android battery optimization where the phone provides that setting.
7. Start the service with `python app.py`.
8. From another device on the home Wi-Fi, verify `http://ANDROID_HOME_LAN_IP:8080/health`.

The server phone must remain powered, connected to home Wi-Fi and online. Android may still stop background processes under battery or thermal management; monitor it during the first tests.

## VK configuration

Set in the private `server/config.py`:
- `VK_ENABLED=True`
- `VK_TOKEN`: a VK access token with permission to read message history, if VK currently grants that access to the application/token type.
- `VK_PEER_ID`: the exact private chat peer ID for the spouse dialog.
- `VK_FROM_ID`: your VK account ID.
- `VK_POLL_SECONDS=20` (default).

On the first poll, the watcher saves the newest message ID as a baseline and does not notify for older messages. On later polls, it emits an event only for a new message from the configured sender in the configured peer. It does not enumerate other dialogs. It also emits an event for a matching message with no text (for example, an attachment-only message).

VK API availability and permissions must be tested with the actual account and token. If VK rejects the method or permission, the integration cannot be considered operational. The app does not read iOS notification banners.

## iPhone BLE relay

1. Install Tailscale on the permanent Android server phone and iPhone 14 Pro. Sign both into the same private tailnet.
2. Use the Android server phone's Tailscale IPv4 address in the iOS app, e.g. `http://100.x.y.z:8080`.
3. Copy `PHONE_TOKEN` from the private server config into the iOS app.
4. Build the SwiftUI source using Xcode on a Mac, sign it and install it on the iPhone. This repository currently contains source code, not a compiled iOS app.
5. Keep the iOS app available and Bluetooth enabled. It scans for Pocket Robot and polls while active. iOS background refresh is opportunistic and does not guarantee immediate delivery while suspended or force-quit.

## Robot home Wi-Fi setup

Copy `firmware/config_local.example.py` to `firmware/config_local.py` and set:
- home SSID and password;
- the Android server's **home LAN IP** as the first network's `server_host`;
- the matching `DEVICE_TOKEN`.

Do not commit `config_local.py` or server tokens.

## API

- `GET /health`
- `POST /api/messages` — authenticated development/test endpoint; not the primary VK workflow.
- `GET /api/robot/messages/next`, `POST /api/robot/messages/ID/ack` — ESP32 queue.
- `GET /api/phone/messages/next`, `POST /api/phone/messages/ID/ack` — iPhone BLE relay queue.
- `GET /api/robot/weather` — current weather from Open-Meteo.
- `GET /api/status` — VK configuration and recent robot presence.

## Release limitations to test

- VK token and private-chat filtering with the actual account.
- Android Termux uptime with screen off and battery optimization settings.
- Home Wi-Fi: server -> ESP32 -> envelope -> MODE clears it.
- Away BLE: server -> Tailscale -> iPhone -> BLE -> envelope -> MODE clears it.
- iOS background behavior on iPhone 14 Pro / iOS 26.4. Do not promise real-time delivery while iOS suspends the app.
- The iPhone-hotspot direct-to-server path is documented but not enabled until a secure public HTTPS endpoint and verified TLS client are implemented.

Do not expose port 8080 directly to the public internet. Keep the server behind Tailscale for the BLE relay.
