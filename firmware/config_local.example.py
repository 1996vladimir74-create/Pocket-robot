# Copy to config_local.py and fill in values. Never commit this file.
# Each network tuple: (SSID, password, server_host_for_that_network).
# Copy to config_local.py and fill in real values. Never commit this file.
# Each entry: (SSID, password, server_host reachable on that network).
# Home Wi-Fi uses the Android server phone home-LAN IP.
# iPhone hotspot direct mode needs a separately configured secure public server
# endpoint and TLS-capable client; it is not enabled in this release.
WIFI_NETWORKS=[
    ("home-wifi", "home-password", "192.168.0.105"),
    # ("iPhone hotspot name", "iPhone hotspot password", "your-secure-server-host"),
]
SERVER_HOST="192.168.0.105"
SERVER_PORT=8080
SERVER_DEVICE_TOKEN="replace-with-device-token"
