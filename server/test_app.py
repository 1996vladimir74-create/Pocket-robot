import os
import sys
import tempfile
import unittest

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import create_app


class ServerApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE": os.path.join(self.tmp.name, "test.db"),
            "ADMIN_TOKEN": "admin-test-token",
            "DEVICE_TOKEN": "device-test-token",
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


if __name__ == "__main__":
    unittest.main()
