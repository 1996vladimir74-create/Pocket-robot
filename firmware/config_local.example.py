# Copy to config_local.py and fill in values. Never commit this file.
# Each network tuple: (SSID, password, server_host_for_that_network).
WIFI_NETWORKS=[
    ("home-wifi","home-password","192.168.0.105"),
    # Future hotspot fallback: connect the Android server phone to the iPhone hotspot too,
    # then put the Android phone's hotspot-LAN address in the third field.
    ("iPhone hotspot name","iPhone hotspot password","172.20.10.2"),
]
SERVER_HOST="192.168.0.105"
SERVER_PORT=8080
SERVER_DEVICE_TOKEN="replace-with-device-token"
