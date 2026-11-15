"""BLE GATT peripheral. iPhone sends UTF-8 text in short framed chunks."""
import bluetooth

SERVICE_UUID="12345678-1234-5678-1234-56789abcdef0"
RX_UUID="12345678-1234-5678-1234-56789abcdef1"
_IRQ_CENTRAL_CONNECT=1
_IRQ_CENTRAL_DISCONNECT=2
_IRQ_GATTS_WRITE=3
_FLAG_READ=0x0002
_FLAG_WRITE=0x0008
_FLAG_WRITE_NO_RESPONSE=0x0004

def _uuid128_le(value):
    return bytes.fromhex(value.replace("-",""))[::-1]

def _adv_payload(name):
    raw=name.encode()[:20]
    return bytearray(b"\x02\x01\x06")+bytearray((len(raw)+1,0x09))+raw+bytearray(b"\x11\x07")+_uuid128_le(SERVICE_UUID)

class BLEBridge:
    def __init__(self,name="PocketRobot"):
        self.ble=bluetooth.BLE()
        self.ble.active(True)
        self.rx_value=None
        self.connected=False
        self.conn_handle=None
        self._chunks={}
        service=(bluetooth.UUID(SERVICE_UUID),((bluetooth.UUID(RX_UUID),_FLAG_READ|_FLAG_WRITE|_FLAG_WRITE_NO_RESPONSE),))
        ((self.rx_handle,),)=self.ble.gatts_register_services((service,))
        self.ble.gatts_set_buffer(self.rx_handle,512,False)
        self.ble.irq(self._irq)
        self._name=name
        self._advertise()
    def _advertise(self):
        self.ble.gap_advertise(250000,adv_data=_adv_payload(self._name),connectable=True)
    def _irq(self,event,data):
        if event==_IRQ_CENTRAL_CONNECT:
            self.conn_handle=data[0]
            self.connected=True
        elif event==_IRQ_CENTRAL_DISCONNECT:
            self.connected=False
            self.conn_handle=None
            self._chunks={}
            self._advertise()
        elif event==_IRQ_GATTS_WRITE:
            conn,attr=data
            if attr!=self.rx_handle: return
            try:
                raw=self.ble.gatts_read(self.rx_handle)
                if len(raw)<7 or raw[0:1]!=b"P": return
                seq=int(raw[1:3].decode(),16)
                part=int(raw[3:5].decode(),16)
                total=int(raw[5:7].decode(),16)
                if total<1 or part>=total: return
                record=self._chunks.get(seq)
                if record is None:
                    record={"total":total,"parts":{}}
                    self._chunks[seq]=record
                if record["total"]!=total: return
                record["parts"][part]=raw[7:]
                if len(record["parts"])==total:
                    joined=b"".join(record["parts"][i] for i in range(total))
                    try: self.rx_value=joined.decode("utf-8").strip()[:240]
                    except Exception: self.rx_value=None
                    self._chunks.pop(seq,None)
            except Exception:
                self.rx_value=None
    def poll(self):
        value=self.rx_value
        self.rx_value=None
        return value
    def status(self):
        return self.connected
