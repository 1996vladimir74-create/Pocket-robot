"""Non-blocking Wi-Fi manager with ordered SSID and server-host failover."""
import time, network, config
class WiFiManager:
    def __init__(self):
        self.wlan=network.WLAN(network.STA_IF)
        self.connected=False; self.connecting=False; self.last_attempt=None
        self.network_index=0; self.active_network_index=None
        networks=getattr(config,"WIFI_NETWORKS",[]) or []
        if not networks and getattr(config,"WIFI_SSID",""):
            networks=[(config.WIFI_SSID,config.WIFI_PASSWORD,getattr(config,"SERVER_HOST",""))]
        self.networks=networks
    @property
    def server_host(self):
        if self.active_network_index is not None:
            item=self.networks[self.active_network_index]
            if len(item)>2 and item[2]: return item[2]
        return getattr(config,"SERVER_HOST","")
    def maintain(self):
        if self.wlan.isconnected():
            if not self.connected:
                self.active_network_index=self.network_index
            self.connected=True; self.connecting=False
            return True
        self.connected=False
        if not self.networks: return False
        now=time.ticks_ms()
        if self.connecting:
            if time.ticks_diff(now,self.last_attempt)>=config.WIFI_CONNECT_TIMEOUT_MS:
                self.connecting=False
                self.network_index=(self.network_index+1)%len(self.networks)
                self.last_attempt=now
            return False
        if self.last_attempt is None or time.ticks_diff(now,self.last_attempt)>=config.WIFI_RETRY_MS:
            item=self.networks[self.network_index]
            ssid,password=item[0],item[1]
            if not ssid:
                self.network_index=(self.network_index+1)%len(self.networks)
                self.last_attempt=now
                return False
            self.last_attempt=now; self.wlan.active(True)
            try:
                self.wlan.connect(ssid,password)
                self.connecting=True
            except Exception:
                self.network_index=(self.network_index+1)%len(self.networks)
        return False
    def connect(self):
        start=time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(),start)<config.WIFI_CONNECT_TIMEOUT_MS:
            if self.maintain(): return True
            time.sleep_ms(100)
        return False
    def status(self):
        return {"connected":self.connected,"ip":self.wlan.ifconfig()[0] if self.wlan.isconnected() else None,"server_host":self.server_host}
