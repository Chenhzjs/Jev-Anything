import json
import threading
import unittest
from http.client import HTTPConnection

from jev_anything import live_server


class LiveApiTests(unittest.TestCase):
    def setUp(self):
        self.old_session = live_server.session
        self.old_busy = live_server.busy
        live_server.session = type("Session", (), {"scenario": "preferences"})()
        live_server.busy = threading.Lock()
        self.server = live_server.ThreadingHTTPServer(("127.0.0.1", 0), live_server.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        live_server.session = self.old_session
        live_server.busy = self.old_busy
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def post(self, path):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        conn.request("POST", path)
        response = conn.getresponse()
        body = json.loads(response.read())
        conn.close()
        return response.status, body

    def test_config_lists_task_board_identity(self):
        self.assertEqual(live_server.SCENARIOS["tasks"]["app"], "task-board")
        self.assertEqual(live_server.SCENARIOS["tasks"]["window_title"], "Jev Task Board")

    def test_run_requires_reset_when_fixture_changes(self):
        status, body = self.post("/api/run?fixture=tasks&goal=archive%20the%20task")
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "fixture_must_be_reset_first")

    def test_error_envelopes_are_json(self):
        status, body = self.post("/api/run?goal=")
        self.assertEqual(status, 400)
        self.assertEqual(body, {"error": "goal_required"})

    def test_unknown_fixture_and_busy_are_explicit(self):
        status, body = self.post("/api/reset?fixture=missing")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "unknown_fixture")
        self.assertIn("preferences", body["fixtures"])

        live_server.busy.acquire()
        try:
            status, body = self.post("/api/reset?fixture=preferences")
        finally:
            live_server.busy.release()
        self.assertEqual(status, 409)
        self.assertEqual(body, {"error": "busy"})

    def test_releasing_replaced_lock_is_safe(self):
        live_server.busy.acquire()
        original = live_server.busy
        live_server.busy = threading.Lock()
        try:
            live_server.release_busy()
        finally:
            live_server.busy = original
        self.assertTrue(original.locked())


if __name__ == "__main__":
    unittest.main()
