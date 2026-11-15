# Pocket Robot — server, weather, VK and phone relay

## Current architecture
- Home: ESP32-S3 -> home Wi-Fi -> Android phone running Flask/SQLite -> weather and messages.
- Away: Android server phone -> private Tailscale network -> iPhone app -> BLE -> ESP32-S3.
- Future fallback: ESP32 Wi-Fi network list supports home router first and iPhone Personal Hotspot second. The hotspot is not required for the initial test.

## Termux setup
1. Install Python in Termux.
2. Clone branch `feature/phone-bridge-weather-vk`.
3. `cd server && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
4. `cp config.example.py config.py`, set three different long tokens and weather coordinates.
5. Keep `VK_ENABLED=False` for the first test.
6. Run `termux-wake-lock` in Termux while testing and exclude Termux from Android battery optimization if the phone offers that setting; Android may otherwise pause the server process.
6. Run `python app.py`; verify `http://ANDROID_LAN_IP:8080/health` from another device on the same Wi-Fi.

## Local home test
- ESP32 config_local.py: home SSID/password, server LAN IP, DEVICE_TOKEN.
- Open the server home page from a second device, enter ADMIN_TOKEN, send a message.
- ESP32 should show the message and keep it on-screen until MODE is pressed.
- The weather screen appears for five seconds after a successful weather refresh, then the face returns.
- Weather endpoint: `GET /api/robot/weather`; source is Open-Meteo, no API key required.

## Remote iPhone relay
The server is hosted on the Android phone. For remote access, both Android and iPhone need to join the same private Tailscale network. Use the Android phone's Tailscale IPv4 as the iOS app URL, e.g. `http://100.x.y.z:8080`. The iOS app uses PHONE_TOKEN, not DEVICE_TOKEN. Keep the server process alive on Android. Do not expose port 8080 directly to the public internet.

The iOS source is in `ios/PocketRobotApp/`. It scans for the ESP32 GATT service, polls the phone queue while active, writes notification text over BLE, and acknowledges the phone queue only after the BLE write succeeds. The app also requests opportunistic iOS background refresh.

## VK setup — optional
- VK integration is off by default.
- If VK provides a valid user token with access to message history for your account, set `VK_ENABLED=True`, `VK_TOKEN`, `VK_PEER_ID` (only the private dialog peer ID) and `VK_FROM_ID` (your VK account ID).
- The watcher calls `messages.getHistory` only for that one peer and forwards only items whose `peer_id` and `from_id` match the configured values. It does not enumerate or store other conversations.
- On first run it saves the latest message ID as a baseline and does not replay old messages.
- VK may reject the token, method or permission. If so, VK delivery is unavailable until an officially supported access method is configured. The app does not read iOS notifications.

## API
- `GET /health`
- `POST /api/messages` (ADMIN_TOKEN) — adds one event to independent robot and phone queues
- `GET /api/robot/messages/next`, `POST /api/robot/messages/ID/ack` (DEVICE_TOKEN)
- `GET /api/phone/messages/next`, `POST /api/phone/messages/ID/ack` (PHONE_TOKEN)
- `GET /api/robot/weather` (DEVICE_TOKEN)
- `GET /api/status`

## Limitations before real-device testing
- iOS does not guarantee periodic background refresh. If the app is force-quit or iOS does not schedule refresh, remote messages may wait until the app is opened.
- Core Bluetooth background mode and state restoration help, but are not a promise of uninterrupted operation.
- VK API access is not guaranteed; verify with the exact token before relying on it.
- No APNs push sender is configured yet. A later APNs implementation requires Apple Developer credentials and server-side configuration.
- This branch has not been built on ESP32 hardware or compiled with Xcode. Validate each link in the chain before calling the system operational.


## iPhone Personal Hotspot fallback
The ESP32 Wi-Fi manager supports an ordered list of networks. Use three values per entry:
`(SSID, password, server_host_on_that_network)`.
For the future hotspot test, the Android phone running the server must also join the iPhone hotspot; otherwise the ESP32 has no local route to the Android server. Find the Android phone's IP while it is connected to the hotspot and place that address in the third field for the iPhone-hotspot entry in `firmware/config_local.py`. The sample `172.20.10.2` is only a placeholder; do not assume it is the assigned address.
No mobile-operator change is inherently required to use Personal Hotspot. If tethering is disabled by the current mobile plan or carrier settings, that restriction must be resolved with the carrier.
