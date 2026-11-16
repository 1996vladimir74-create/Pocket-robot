"""Copy to config.py and replace every token. Never commit config.py."""
HOST="0.0.0.0"
PORT=8080
ADMIN_TOKEN="change-this-admin-token"
DEVICE_TOKEN="change-this-device-token"
PHONE_TOKEN="change-this-phone-token"

# Open-Meteo coordinates; change to your home location.
WEATHER_LATITUDE=60.1699
WEATHER_LONGITUDE=24.9384
WEATHER_TIMEZONE="auto"

# VK private-dialog filter. Keep disabled until a valid VK user token is available.
VK_ENABLED=False
VK_TOKEN=""
VK_API_VERSION="5.199"
VK_PEER_ID=0
VK_FROM_ID=0
VK_POLL_SECONDS=20
