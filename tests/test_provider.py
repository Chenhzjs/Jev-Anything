import unittest
from unittest.mock import patch, Mock
import requests
from jev_anything.jev import JevClient, JevConfig, JevError


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.client = JevClient(JevConfig(api_key="test-only", timeout=0.01))

    def test_timeout(self):
        with patch("jev_anything.jev.requests.post", side_effect=requests.Timeout("timed out")):
            with self.assertRaises(JevError):
                self.client.decide(state={}, questions={"a": {}})

    def test_invalid_bodies(self):
        for body in ([], None, {"answers": []}, {}):
            with self.subTest(body=body), patch("jev_anything.jev.requests.post") as post:
                post.return_value = Mock(json=Mock(return_value=body))
                with self.assertRaises(JevError):
                    self.client.decide(state={}, questions={"a": {}})

    def test_metadata(self):
        with patch("jev_anything.jev.requests.post") as post:
            post.return_value = Mock(json=Mock(return_value={"id": "request-1", "answers": {}, "usage": {"cost": 0.01}}))
            self.client.decide(state={}, questions={"a": {}})
            self.assertEqual(self.client.metadata["request_id"], "request-1")
            self.assertNotIn("api_key", self.client.metadata)
