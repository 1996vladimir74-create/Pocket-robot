"""External integrations using only Python standard library."""
import json, os, urllib.parse, urllib.request

class WeatherClient:
    def current(self,latitude,longitude,timezone="auto"):
        query=urllib.parse.urlencode({"latitude":latitude,"longitude":longitude,"current":"temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m","timezone":timezone})
        req=urllib.request.Request("https://api.open-meteo.com/v1/forecast?"+query,headers={"User-Agent":"PocketRobot/1.0"})
        with urllib.request.urlopen(req,timeout=8) as response: data=json.loads(response.read().decode())
        c=data.get("current",{})
        return {"temperature_c":c.get("temperature_2m"),"feels_like_c":c.get("apparent_temperature"),"humidity_percent":c.get("relative_humidity_2m"),"wind_kmh":c.get("wind_speed_10m"),"weather_code":c.get("weather_code"),"time":c.get("time"),"source":"Open-Meteo"}

class VKDialogWatcher:
    """Poll one VK peer and emit a content-free event for the configured sender."""
    def __init__(self,token,peer_id,from_id,version,state_file,on_message):
        self.token=token; self.peer_id=int(peer_id); self.from_id=int(from_id); self.version=version
        self.state_file=state_file; self.on_message=on_message; self.last_id=self._load_state()
    def _load_state(self):
        try:
            with open(self.state_file,"r",encoding="utf-8") as f: return int(json.load(f).get("last_message_id",0))
        except Exception: return 0
    def _save_state(self):
        os.makedirs(os.path.dirname(self.state_file),exist_ok=True)
        tmp=self.state_file+".tmp"
        with open(tmp,"w",encoding="utf-8") as f: json.dump({"last_message_id":self.last_id},f)
        os.replace(tmp,self.state_file)
    def _api(self,method,params):
        p=dict(params); p.update({"access_token":self.token,"v":self.version})
        req=urllib.request.Request("https://api.vk.com/method/"+method,data=urllib.parse.urlencode(p).encode(),headers={"User-Agent":"PocketRobot/1.0"})
        with urllib.request.urlopen(req,timeout=10) as response: data=json.loads(response.read().decode())
        if "error" in data: raise RuntimeError("VK API error: "+str(data["error"].get("error_msg","unknown")))
        return data.get("response",{})
    def poll_once(self):
        response=self._api("messages.getHistory",{"peer_id":self.peer_id,"count":20,"offset":0,"rev":0})
        items=response.get("items",[]) if isinstance(response,dict) else []
        if not items: return 0
        if self.last_id==0:
            self.last_id=max(int(x.get("id",0)) for x in items); self._save_state(); return 0
        fresh=[x for x in items if int(x.get("id",0))>self.last_id]
        count=0
        for item in sorted(fresh,key=lambda x:int(x.get("id",0))):
            mid=int(item.get("id",0))
            if (int(item.get("peer_id", 0)) == self.peer_id
                    and int(item.get("from_id", 0)) == self.from_id):
                # Only a notification event is forwarded; no message content.
                self.on_message()
                count += 1
            self.last_id=max(self.last_id,mid)
        if fresh: self._save_state()
        return count
