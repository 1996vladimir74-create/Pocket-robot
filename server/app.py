"""Pocket Robot message server (Flask, SQLite)."""
import os
from flask import Flask, jsonify, request, Response
from database import init_db, enqueue_message, lease_next_message, acknowledge_message, list_messages


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.path.join(os.path.dirname(__file__), "data", "robot.db"),
        ADMIN_TOKEN=os.environ.get("POCKET_ROBOT_ADMIN_TOKEN", ""),
        DEVICE_TOKEN=os.environ.get("POCKET_ROBOT_DEVICE_TOKEN", ""),
        MESSAGE_MAX_LENGTH=240,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    init_db(app.config["DATABASE"])

    def authorized(expected):
        supplied = request.headers.get("Authorization", "")
        return bool(expected) and supplied == "Bearer " + expected

    @app.get("/")
    def index():
        return Response(INDEX_HTML, mimetype="text/html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "pocket-robot-server"})

    @app.post("/api/messages")
    def send_message():
        if not authorized(app.config["ADMIN_TOKEN"]):
            return jsonify({"error": "unauthorized"}), 401
        data = request.get_json(silent=True) or {}
        message = data.get("text", "")
        if not isinstance(message, str):
            return jsonify({"error": "text must be a string"}), 400
        message = message.strip()
        if not message:
            return jsonify({"error": "message is empty"}), 400
        if len(message) > app.config["MESSAGE_MAX_LENGTH"]:
            return jsonify({"error": "message is too long"}), 400
        message_id = enqueue_message(app.config["DATABASE"], message)
        return jsonify({"ok": True, "id": message_id}), 201

    @app.get("/api/robot/messages/next")
    def next_message():
        if not authorized(app.config["DEVICE_TOKEN"]):
            return jsonify({"error": "unauthorized"}), 401
        item = lease_next_message(app.config["DATABASE"])
        return jsonify({"message": item})

    @app.post("/api/robot/messages/<int:message_id>/ack")
    def ack_message(message_id):
        if not authorized(app.config["DEVICE_TOKEN"]):
            return jsonify({"error": "unauthorized"}), 401
        changed = acknowledge_message(app.config["DATABASE"], message_id)
        if not changed:
            return jsonify({"error": "message not found or already acknowledged"}), 404
        return jsonify({"ok": True, "id": message_id})

    @app.get("/api/messages/recent")
    def recent_messages():
        if not authorized(app.config["ADMIN_TOKEN"]):
            return jsonify({"error": "unauthorized"}), 401
        return jsonify({"messages": list_messages(app.config["DATABASE"], limit=20)})

    return app


INDEX_HTML = """<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pocket Robot — сообщения</title>
<style>
body{font:16px system-ui,sans-serif;max-width:620px;margin:40px auto;padding:0 16px;background:#111827;color:#f3f4f6}
main{background:#1f2937;padding:24px;border-radius:14px}input,textarea,button{box-sizing:border-box;width:100%;padding:12px;margin:8px 0;border-radius:8px;border:1px solid #4b5563;font:inherit}
input,textarea{background:#111827;color:white}button{background:#2563eb;color:white;border:0;font-weight:600}small,#result{color:#9ca3af}
</style><main><h1>Pocket Robot</h1><p>Отправка тестового сообщения на робот.</p>
<label>Ключ отправителя</label><input id="token" type="password" autocomplete="off" placeholder="Admin token">
<label>Сообщение</label><textarea id="message" maxlength="240" rows="4" placeholder="Например: Привет! Проверь уведомление."></textarea>
<button id="send">Отправить сообщение</button><p id="result" role="status">Сервер готов.</p>
<small>Ключ используется только в этом браузере и не сохраняется сервером.</small></main>
<script>
document.getElementById('send').addEventListener('click',async()=>{
 const result=document.getElementById('result');
 const token=document.getElementById('token').value;
 const text=document.getElementById('message').value;
 if(!token||!text.trim()){result.textContent='Введите ключ и сообщение.';return;}
 try{
  const r=await fetch('/api/messages',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({text})});
  const data=await r.json();
  result.textContent=r.ok?'Сообщение добавлено в очередь. ID: '+data.id:'Ошибка: '+(data.error||r.status);
  if(r.ok)document.getElementById('message').value='';
 }catch(e){result.textContent='Не удалось связаться с сервером: '+e;}
});
</script></html>"""


if __name__ == "__main__":
    from config import ADMIN_TOKEN, DEVICE_TOKEN, HOST, PORT
    if not ADMIN_TOKEN or not DEVICE_TOKEN or "change-this" in ADMIN_TOKEN or "change-this" in DEVICE_TOKEN:
        raise SystemExit("Set unique ADMIN_TOKEN and DEVICE_TOKEN in server/config.py first.")
    application = create_app({"ADMIN_TOKEN": ADMIN_TOKEN, "DEVICE_TOKEN": DEVICE_TOKEN})
    application.run(host=HOST, port=PORT, debug=False)
