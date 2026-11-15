"""BLE GATT peripheral bridge for iPhone -> ESP32 notification delivery.
The iPhone app writes UTF-8 notification text to the RX characteristic.
"""
import bluetooth, struct, time

SERVICE_UUID="12345678-1234-5678-1234-56789abcdef0"
RX_UUID="12345678-1234-5678-1234-56789abcdef1"
_IRQ_CENTRAL_CONNECT=1
_IRQ_CENTRAL_DISCONNECT=2
_IRQ_GATTS_WRITE=3
_FLAG_READ=0x0002
_FLAG_WRITE=0x0008
_FLAG_WRITE_NO_RESPONSE=0x0004

def _adv_payload(name):
    name=name.encode()
    return (bytearray(b"\x02\x01\x06")+
            bytearray((len(name)+1,0x09))+name+
            bytearray(b"\x11\x07")+_uuid128_le(SERVICE_UUID))

def _uuid128_le(value):
    raw=bytes.fromhex(value.replace("-",""))
    return raw[::-1]

class BLEBridge:
    def __init__(self,name="PocketRobot"):
        self.ble=bluetooth.BLE(); self.ble.active(True)
        self.rx_value=None; self.connected=False; self.conn_handle=None
        self.service=(bluetooth.UUID(SERVICE_UUID),((bluetooth.UUID(RX_UUID),_FLAG_READ|_FLAG_WRITE|_FLAG_WRITE_NO_RESPONSE),))
        ((self.rx_handle,),)=self.ble.gatts_register_services((self.service,))
        self.ble.irq(self._irq)
        self._name=name
        self._advertise()
    def _advertise(self):
        self.ble.gap_advertise(250000,adv_data=_adv_payload(self._name),connectable=True)
    def _irq(self,event,data):
        if event==_IRQ_CENTRAL_CONNECT:
            self.conn_handle=data[0]; self.connected=True
        elif event==_IRQ_CENTRAL_DISCONNECT:
            self.connected=False; self.conn_handle=None; self._advertise()
        elif event==_IRQ_GATTS_WRITE:
            conn,attr=data
            if attr==self.rx_handle:
                try:
                    raw=self.ble.gatts_read(self.rx_handle)
                    self.rx_value=raw.decode("utf-8").strip()[:240]
                except Exception:
                    self.rx_value=None
    def poll(self):
        value=self.rx_value; self.rx_value=None
        return value
    def status(self):
        return self.connected
