from dataclasses import replace
import unittest
from unittest.mock import Mock
from jev_anything.plugin import Candidate, Observation, DecisionPlugin, CapabilityUnavailable


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.candidate = Candidate("enable", "Enable", "click", "scope", "before", "enabled")
        self.before = Observation("test", "disabled", "before", "scope", (self.candidate,))
        self.after = replace(self.before, scene="enabled", generation="after")
        self.backend = Mock()
        self.backend.snapshot.side_effect = [self.before, self.before, self.after]
        self.backend.verify.return_value = True
        self.provider = Mock(model="test", metadata={})
        self.provider.decide.return_value = {"action": {"type": "choice", "choice": "enable"}}
        self.plugin = DecisionPlugin(self.backend)

    def run_once(self, **kwargs):
        return self.plugin.run("enable", self.provider, request_id="request", **kwargs)

    def test_confirmed_and_duplicate_request(self):
        first = self.run_once()
        self.assertEqual(first.outcome.status, "confirmed")
        self.assertIs(self.run_once(), first)
        self.backend.execute.assert_called_once()
        self.provider.decide.assert_called_once()
        with self.assertRaises(ValueError):
            self.plugin.run("other", self.provider, request_id="request")

    def test_readback_failure_never_retries(self):
        self.backend.snapshot.side_effect = [self.before, self.before, TimeoutError("readback")]
        result = self.run_once()
        self.assertEqual(result.outcome.status, "unknown")
        self.assertEqual(result.outcome.effect, "unknown")
        self.assertIs(self.run_once(), result)
        self.backend.execute.assert_called_once()

    def test_stale_scope_candidates_and_expiry(self):
        for index, state in enumerate([replace(self.before, generation="changed"),
                      replace(self.before, interaction_scope="changed"),
                      replace(self.before, candidates=()), self.before]):
            with self.subTest(state=state):
                self.setUp()
                if index == 3:
                    self.plugin.max_age = -1
                self.backend.snapshot.side_effect = [self.before, state]
                self.assertEqual(self.run_once().outcome.status, "rejected")
                self.backend.execute.assert_not_called()

    def test_pause_during_provider_call(self):
        paused = [False]
        def decide(**kwargs):
            paused[0] = True
            return {"action": {"type": "choice", "choice": "enable"}}
        self.provider.decide.side_effect = decide
        self.assertEqual(self.run_once(cancelled=lambda: paused[0]).outcome.status, "rejected")
        self.backend.execute.assert_not_called()

    def test_capability_failure(self):
        self.backend.validate.side_effect = CapabilityUnavailable("No binding")
        self.assertEqual(self.run_once().outcome.status, "unsupported")
        self.provider.decide.assert_not_called()
        self.backend.execute.assert_not_called()

    def test_invalid_unknown_abstain_and_timeout(self):
        for answer, status in [({}, "failed"),
                               ({"action": {"type": "choice", "choice": "fake"}}, "rejected"),
                               ({"action": {"type": "choice", "choice": "abstain"}}, "abstained")]:
            self.setUp()
            self.provider.decide.return_value = answer
            self.assertEqual(self.run_once().outcome.status, status)
            self.backend.execute.assert_not_called()
        self.setUp()
        self.provider.decide.side_effect = TimeoutError("provider timeout")
        self.assertEqual(self.run_once().outcome.status, "failed")
        self.backend.execute.assert_not_called()

    def test_execution_failure_is_unknown(self):
        self.backend.execute.side_effect = TimeoutError("delivery uncertain")
        self.assertEqual(self.run_once().outcome.delivery, "unknown")
        self.assertEqual(self.run_once().outcome.status, "unknown")
        self.backend.execute.assert_called_once()

    def test_risk_and_generation_are_validated(self):
        for field, value in [("risk", "external"), ("scope", "other"), ("generation", "other")]:
            self.setUp()
            before = replace(self.before, candidates=(replace(self.candidate, **{field: value}),))
            self.backend.snapshot.side_effect = [before, before]
            self.assertEqual(self.run_once().outcome.status, "rejected")
            self.backend.execute.assert_not_called()

    def test_unobservable_effect(self):
        self.backend.verify.return_value = None
        self.assertEqual(self.run_once().outcome.status, "unknown")

    def test_empty_candidates(self):
        self.backend.snapshot.side_effect = [replace(self.before, candidates=())]
        self.assertEqual(self.run_once().outcome.status, "abstained")
        self.provider.decide.assert_not_called()

    def test_scope_change_on_readback_is_unknown(self):
        self.backend.snapshot.side_effect = [self.before, self.before, replace(self.after, interaction_scope="other")]
        self.assertEqual(self.run_once().outcome.status, "unknown")

    def test_outcomes_have_stable_error_codes(self):
        self.provider.decide.return_value = {"action": {"type": "choice", "choice": "abstain"}}
        result = self.run_once()
        self.assertEqual(result.outcome.error_code, "model_abstained")
        self.assertEqual(result.to_dict()["version"], "run.v1")
