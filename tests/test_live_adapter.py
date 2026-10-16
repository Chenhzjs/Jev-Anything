import unittest
from unittest.mock import patch, Mock
from jev_anything.live import LiveSession
from jev_anything.plugin import CapabilityUnavailable, Candidate


class AdapterTests(unittest.TestCase):
    def test_dispatch_does_not_send_escape_to_main_screen(self):
        session = LiveSession.__new__(LiveSession)
        session.terminal = Mock()
        session.wait = Mock()
        session.pump = Mock(return_value="> Enable Action: click")
        session.select(Candidate("a", "Enable", "Action: click", "s", "g", None), invoke=True)
        sent = [call.args[0] for call in session.terminal.send.call_args_list]
        self.assertEqual(sent, ["\x1bOR", "Enable", "\r"])

    def test_missing_export_is_explicit(self):
        session = LiveSession.__new__(LiveSession)
        session.session_id = "scope"
        session.scenario = "preferences"
        with patch("jev_anything.live.subprocess.run") as run:
            run.return_value.stdout = 'Scene title="Jev Anything Fixture"'
            with self.assertRaises(CapabilityUnavailable):
                session.snapshot()

    def test_checked_toggle_is_removed(self):
        session = LiveSession.__new__(LiveSession)
        session.session_id = "scope"
        session.scenario = "preferences"
        with patch("jev_anything.live.subprocess.run") as run:
            run.return_value.stdout = ('Scene title="Jev Anything Fixture"\n'
                'label: "Enable dark mode", checked: true binding=1\n'
                'label: "Open settings" binding=2\n'
                'label: "Request background refresh" binding=3')
            self.assertNotIn("c-theme", [c.id for c in session.snapshot().candidates])
