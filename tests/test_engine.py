import unittest

from jev_anything.engine import DemoEngine
from jev_anything.jev import JevError


class Provider:
    model = "test"

    def __init__(self, answer):
        self.answer = answer

    def decide(self, **kwargs):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class LoopTests(unittest.TestCase):
    def run_case(self, answer, stale=False):
        engine = DemoEngine()
        engine._provider = Provider(answer)
        events = list(engine.run("test", force_stale=stale))
        return engine, events, events[-1]["outcome"]

    def test_errors_are_not_abstentions(self):
        for answer in (JevError("timeout"), {}, {"action": {"choice": 12}}):
            with self.subTest(answer=answer):
                engine, events, outcome = self.run_case(answer)
                self.assertEqual(outcome["status"], "failed")
                self.assertFalse(any(e["kind"] == "dispatch" for e in events))

    def test_abstain(self):
        _, events, outcome = self.run_case({"action": {"choice": "abstain"}})
        self.assertEqual(outcome["status"], "abstained")
        self.assertFalse(any(e["kind"] == "dispatch" for e in events))

    def test_stale_and_unknown_are_blocked(self):
        for choice, stale in (("c-theme", True), ("invented", False)):
            engine, events, outcome = self.run_case({"action": {"choice": choice}}, stale)
            self.assertEqual(outcome["status"], "rejected")
            self.assertFalse(engine.dark_mode)
            self.assertFalse(any(e["kind"] == "dispatch" for e in events))

    def test_unimplemented_close_is_not_confirmed(self):
        _, _, outcome = self.run_case({"action": {"choice": "c-close"}})
        self.assertEqual(outcome["status"], "unknown")

    def test_simulated_success_has_explicit_provenance(self):
        engine, _, outcome = self.run_case({"action": {"choice": "c-theme"}})
        self.assertTrue(engine.dark_mode)
        self.assertEqual(outcome["delivery"], "simulated")


if __name__ == "__main__":
    unittest.main()
