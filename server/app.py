"""Pocket Robot server: device queues, phone relay, weather and optional VK polling."""
import os, threading, time
from flask import Flask, jsonify, request, Response
from database import (init_db, enqueue_message, lease_next_message,
    lease_next_phone_message, acknowledge_message, acknowledge_phone_message, list_messages)
from integrations import WeatherClient, VKDialogWatcher

def create_app(test_config=None):
    app=Flask(__name__)
    base=os.path.dirname(__file__)
    app.config.update(
        DATABASE=os.path.join(base,"data","robot.db"),
        ADMIN_TOKEN=os.environ.get("POCKET_ROBOT_ADMIN_TOKEN",""),
        DEVICE_TOKEN=os.environ.get("POCKET_ROBOT_DEVICE_TOKEN",""),
        PHONE_TOKEN=os.environ.get("POCKET_ROBOT_PHONE_TOKEN",""),
        MESSAGE_MAX_LENGTH=240,
        WEATHER_LATITUDE=60.1699, WEATHER_LONGITUDE=24.9384,
        WEATHER_TIMEZONE="auto",
        VK_ENABLED=False, VK_TOKEN="", VK_API_VERSION="5.199",
        VK_PEER_ID=0, VK_FROM_ID=0, VK_POLL_SECONDS=20,
        VK_STATE_FILE=os.path.join(base,"data","vk_state.json"),
    )
    if test_config: app.config.update(test_config)
    os.makedirs(os.path.dirname(app.config["DATABASE"]),exist_ok=True)
    init_db(app.config["DATABASE"])
    weather=WeatherClient()
    watcher=None
    watcher_thread=None

    def authorized(token):
        return bool(token) and request.headers.get("Authorization","")== "Bearer "+token

    @app.get("/")
    def index(): return Response(INDEX_HTML,mimetype="text/html")

    @app.get("/health")
    def health(): return jsonify({"status":"ok","service":"pocket-robot-server"})

    @app.post("/api/messages")
    def send_message():
        if not authorized(app.config["ADMIN_TOKEN"]): return jsonify(error="unauthorized"),401
        data=request.get_json(silent=True) or {}; message=data.get("text","")
        if not isinstance(message,str): return jsonify(error="text must be a string"),400
        message=message.strip()
        if not message: return jsonify(error="message is empty"),400
        if len(message)>app.config["MESSAGE_MAX_LENGTH"]: return jsonify(error="message is too long"),400
        mid=enqueue_message(app.config["DATABASE"],message)
        return jsonify(ok=True,id=mid),201

    @app.get("/api/robot/messages/next")
    def robot_next():
        if not authorized(app.config["DEVICE_TOKEN"]): return jsonify(error="unauthorized"),401
        return jsonify(message=lease_next_message(app.config["DATABASE"]))

    @app.post("/api/robot/messages/<int:mid>/ack")
    def robot_ack(mid):
        if not authorized(app.config["DEVICE_TOKEN"]): return jsonify(error="unauthorized"),401
        if not acknowledge_message(app.config["DATABASE"],mid): return jsonify(error="not found or already acknowledged"),404
        return jsonify(ok=True,id=mid)

    @app.get("/api/phone/messages/next")
    def phone_next():
        if not authorized(app.config["PHONE_TOKEN"]): return jsonify(error="unauthorized"),401
        return jsonify(message=lease_next_phone_message(app.config["DATABASE"]))

    @app.post("/api/phone/messages/<int:mid>/ack")
    def phone_ack(mid):
        if not authorized(app.config["PHONE_TOKEN"]): return jsonify(error="unauthorized"),401
        if not acknowledge_phone_message(app.config["DATABASE"],mid): return jsonify(error="not found or already acknowledged"),404
        return jsonify(ok=True,id=mid)

    @app.get("/api/robot/weather")
    def robot_weather():
        if not authorized(app.config["DEVICE_TOKEN"]): return jsonify(error="unauthorized"),401
        try:
            data=weather.current(app.config["WEATHER_LATITUDE"],app.config["WEATHER_LONGITUDE"],app.config["WEATHER_TIMEZONE"])
            return jsonify(data)
        except Exception as exc:
            return jsonify(error="weather_unavailable",detail=str(exc)),502

    @app.get("/api/messages/recent")
    def recent():
        if not authorized(app.config["ADMIN_TOKEN"]): return jsonify(error="unauthorized"),401
        return jsonify(messages=list_messages(app.config["DATABASE"]))

    @app.get("/api/status")
    def status():
        return jsonify(vk_enabled=bool(app.config["VK_ENABLED"] and app.config["VK_TOKEN"] and app.config["VK_PEER_ID"] and app.config["VK_FROM_ID"]),
                       weather_configured=True, phone_relay=bool(app.config["PHONE_TOKEN"]))

    # VK watcher is explicitly opt-in. It only requests history for one peer_id,
    # then accepts records whose from_id equals the configured sender.
    if (not app.config.get("TESTING") and app.config["VK_ENABLED"] and app.config["VK_TOKEN"]
        and app.config["VK_PEER_ID"] and app.config["VK_FROM_ID"]):
        watcher=VKDialogWatcher(
            token=app.config["VK_TOKEN"], peer_id=int(app.config["VK_PEER_ID"]),
            from_id=int(app.config["VK_FROM_ID"]), version=app.config["VK_API_VERSION"],
            state_file=app.config["VK_STATE_FILE"],
            on_message=lambda text: enqueue_message(app.config["DATABASE"],text))
        def watch_loop():
            while True:
                try: watcher.poll_once()
                except Exception as exc: app.logger.warning("VK poll failed: %s",exc)
                time.sleep(max(10,int(app.config["VK_POLL_SECONDS"])))
        watcher_thread=threading.Thread(target=watch_loop,daemon=True,name="vk-dialog-watcher")
        watcher_thread.start()

    return app

INDEX_HTML="""<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pocket Robot</title><style>body{font:16px system-ui;max-width:620px;margin:35px auto;padding:0 16px;background:#111827;color:#f3f4f6}main{background:#1f2937;padding:22px;border-radius:14px}input,textarea,button{box-sizing:border-box;width:100%;padding:12px;margin:8px 0;border-radius:8px;border:1px solid #4b5563;font:inherit}input,textarea{background:#111827;color:white}button{background:#2563eb;color:white;border:0}</style>
<main><h1>Pocket Robot</h1><p>Тестовая отправка уведомления.</p><input id="token" type="password" placeholder="ADMIN_TOKEN"><textarea id="message" maxlength="240" rows="4" placeholder="Сообщение"></textarea><button id="send">Отправить</button><p id="result">Сервер готов.</p></main>
<script>send.onclick=async()=>{try{let r=await fetch('/api/messages',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token.value},body:JSON.stringify({text:message.value})});let j=await r.json();result.textContent=r.ok?'Добавлено, ID '+j.id:'Ошибка '+(j.error||r.status)}catch(e){result.textContent=String(e)}}</script></html>"""

if __name__=="__main__":
    from config import ADMIN_TOKEN,DEVICE_TOKEN,PHONE_TOKEN,HOST,PORT
    for value in (ADMIN_TOKEN,DEVICE_TOKEN,PHONE_TOKEN):
        if not value or "change-this" in value: raise SystemExit("Set unique tokens in server/config.py")
    create_app({"ADMIN_TOKEN":ADMIN_TOKEN,"DEVICE_TOKEN":DEVICE_TOKEN,"PHONE_TOKEN":PHONE_TOKEN}).run(host=HOST,port=PORT,debug=False)
