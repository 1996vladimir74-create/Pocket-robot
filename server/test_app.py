import os
import sys
import tempfile
import unittest

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import create_app
from integrations import VKDialogWatcher


class ServerApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE": os.path.join(self.tmp.name, "test.db"),
            "ADMIN_TOKEN": "admin-test-token",
            "DEVICE_TOKEN": "device-test-token",
            "PHONE_TOKEN": "phone-test-token",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_admin_can_enqueue_and_robot_can_receive_and_ack(self):
        sent = self.client.post(
            "/api/messages",
            headers={"Authorization": "Bearer admin-test-token"},
            json={"text": "Hello Pocket Robot"},
        )
        self.assertEqual(sent.status_code, 201)
        message_id = sent.get_json()["id"]

        received = self.client.get(
            "/api/robot/messages/next",
            headers={"Authorization": "Bearer device-test-token"},
        )
        self.assertEqual(received.status_code, 200)
        self.assertEqual(received.get_json()["message"]["id"], message_id)
        self.assertEqual(received.get_json()["message"]["text"], "Hello Pocket Robot")

        ack = self.client.post(
            "/api/robot/messages/{}/ack".format(message_id),
            headers={"Authorization": "Bearer device-test-token"},
            json={"received": True},
        )
        self.assertEqual(ack.status_code, 200)

        empty = self.client.get(
            "/api/robot/messages/next",
            headers={"Authorization": "Bearer device-test-token"},
        )
        self.assertIsNone(empty.get_json()["message"])

    def test_acknowledging_phone_relay_retires_both_queue_copies(self):
        sent = self.client.post(
            "/api/messages",
            headers={"Authorization": "Bearer admin-test-token"},
            json={"text": "Phone relay test"},
        )
        self.assertEqual(sent.status_code, 201)

        phone_item = self.client.get(
            "/api/phone/messages/next",
            headers={"Authorization": "Bearer phone-test-token"},
        ).get_json()["message"]
        self.assertEqual(phone_item["text"], "Phone relay test")

        phone_ack = self.client.post(
            "/api/phone/messages/{}/ack".format(phone_item["id"]),
            headers={"Authorization": "Bearer phone-test-token"},
            json={},
        )
        self.assertEqual(phone_ack.status_code, 200)

        robot_item = self.client.get(
            "/api/robot/messages/next",
            headers={"Authorization": "Bearer device-test-token"},
        ).get_json()["message"]
        self.assertIsNone(robot_item)

    def test_wrong_tokens_are_rejected(self):
        response = self.client.post(
            "/api/messages",
            headers={"Authorization": "Bearer wrong"},
            json={"text": "Should not be stored"},
        )
        self.assertEqual(response.status_code, 401)

    def test_empty_message_is_rejected(self):
        response = self.client.post(
            "/api/messages",
            headers={"Authorization": "Bearer admin-test-token"},
            json={"text": "   "},
        )
        self.assertEqual(response.status_code, 400)

    def test_robot_presence_selects_direct_transport(self):
        status = self.client.get("/api/status").get_json()
        self.assertFalse(status["robot_online"])
        self.client.get(
            "/api/robot/messages/next",
            headers={"Authorization": "Bearer device-test-token"},
        )
        status = self.client.get("/api/status").get_json()
        self.assertTrue(status["robot_online"])

    def test_vk_watcher_emits_event_without_message_text(self):
        state_file = os.path.join(self.tmp.name, "vk_state.json")
        events = []
        watcher = VKDialogWatcher(
            token="test", peer_id=2000000123, from_id=42, version="5.199",
            state_file=state_file, on_message=lambda: events.append("NEW_MESSAGE"),
        )
        responses = [
            {"items": [{"id": 10, "peer_id": 2000000123, "from_id": 7, "text": "old"}]},
            {"items": [
                {"id": 12, "peer_id": 2000000123, "from_id": 99, "text": "other sender"},
                {"id": 11, "peer_id": 2000000123, "from_id": 42, "attachments": [{"type": "photo"}]},
            ]},
        ]
        watcher._api = lambda method, params: responses.pop(0)
        self.assertEqual(watcher.poll_once(), 0)
        self.assertEqual(watcher.poll_once(), 1)
        self.assertEqual(events, ["NEW_MESSAGE"])


if __name__ == "__main__":
    unittest.main()
