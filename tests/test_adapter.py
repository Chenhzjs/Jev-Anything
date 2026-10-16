import unittest

from jev_anything.adapter import ActionSpec, Gui2TuiSceneAdapter
from jev_anything.plugin import CapabilityUnavailable


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = Gui2TuiSceneAdapter(
            application="demo", window_title="Demo Window", scope="scope-1",
            actions=(ActionSpec("save", "Save", "Saved"),
                     ActionSpec("skip", "Skip", "Skipped")),
        )

    def test_structured_scene_becomes_candidates(self):
        observation = self.adapter.observe(
            'Scene title="Demo Window"\n'
            'Element 1 kind=Button { label: "Save" } binding=runtime:1\n'
            'Element 2 kind=Button { label: "Skip" } binding=runtime:2')
        self.assertEqual([candidate.id for candidate in observation.candidates], ["save", "skip"])
        self.assertEqual(observation.interaction_scope, "scope-1")
        self.assertEqual(len(observation.generation), 16)
        self.assertIsInstance(observation.observed_at, float)

    def test_missing_executable_actions_are_capability_gap(self):
        with self.assertRaisesRegex(CapabilityUnavailable, "no configured executable"):
            self.adapter.observe('Scene title="Demo Window"\nElement 1 kind=Text { text: "Read only" }')

    def test_checked_action_is_not_offered(self):
        observation = self.adapter.observe(
            'Scene title="Demo Window"\n'
            'Element 1 kind=Checkbox { label: "Save", checked: true } binding=runtime:1\n'
            'Element 2 kind=Button { label: "Skip" } binding=runtime:2')
        self.assertEqual([candidate.id for candidate in observation.candidates], ["skip"])


if __name__ == "__main__":
    unittest.main()
