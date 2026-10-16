"""Verify the provider's actual choice wire format without exposing credentials."""

import json
from test_jev import load_dotenv
from jev_anything import JevClient

load_dotenv()
client = JevClient()
answers = client.decide(
    state={"goal": "Enable dark mode", "controls": {"dark_mode": False}},
    questions={"action": {
        "type": "choice",
        "instructions": "Choose exactly one candidate ID: c-theme, c-settings, c-refresh, abstain.",
        "criteria": {"c-theme": "Enable dark mode", "c-settings": "Open settings", "c-refresh": "Request background refresh", "abstain": "No supported action completes the goal"},
    }},
)
print(json.dumps(answers))
