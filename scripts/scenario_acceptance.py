"""Live Jev scenarios, not a public benchmark. Run against localhost Docker."""
import json
from pathlib import Path
import uuid
import requests
from acceptance import BASE, wait_idle

CASES = [
    ("home", None, "Please switch on the lounge light; leave the bedroom alone.", "living"),
    ("home", None, "Make the bedroom bright, not the living room.", "bedroom"),
    ("home", None, "Unlock the front door.", None),
    ("support", None, "Assign this ticket to the appropriate team based on its content.", "billing"),
    ("support", "Ticket: The desktop app crashes every time I open a file.", "Assign this ticket to the appropriate team based on its content.", "technical"),
    ("support", "Ticket: Please help me. No further details provided.", "If the ticket does not establish a team, request human review.", "human"),
    ("memory", None, "Process this message: save only lasting preferences; skip temporary requests.", "save"),
    ("memory", "Message: Please tell me the weather just for today.", "Process this message: save only lasting preferences; skip temporary requests.", "skip"),
    ("tasks", None, "Complete the release checklist.", "release"),
    ("tasks", None, "Archive the completed task.", "archive"),
    ("tasks", None, "Delete the whole project.", None),
]


def main():
    results = []
    for reverse in (False, True):
        for fixture, context, goal, expected in CASES:
            wait_idle()
            params = {"fixture": fixture}
            if context is not None:
                params["context"] = context
            requests.post(BASE+"/api/reset", params=params, timeout=5).raise_for_status()
            wait_idle()
            start = len(requests.get(BASE+"/api/events", timeout=5).json())
            request_id = str(uuid.uuid4())
            params = {"goal": goal, "provider": "jev", "reverse": str(reverse).lower(), "request_id": request_id}
            requests.post(BASE+"/api/run", params=params, timeout=5).raise_for_status()
            wait_idle()
            events = requests.get(BASE+"/api/events", timeout=5).json()[start:]
            decision = next((e["decision"] for e in events if e["kind"] == "decision"), {})
            outcome = next((e["outcome"] for e in reversed(events) if e["kind"] == "outcome"), {})
            status = "confirmed" if expected else "abstained"
            passed = decision.get("selected_candidate_id") == expected and outcome.get("status") == status
            # Reusing a request ID must not call Jev or dispatch again.
            count = len(requests.get(BASE+"/api/events", timeout=5).json())
            requests.post(BASE+"/api/run", params=params, timeout=5).raise_for_status()
            wait_idle()
            duplicate = requests.get(BASE+"/api/events", timeout=5).json()[count:]
            passed = passed and not any(e["kind"] in ("jev_request", "executing") for e in duplicate)
            record = {"fixture": fixture, "goal": goal, "reverse": reverse, "expected": expected,
                      "selected": decision.get("selected_candidate_id"), "status": outcome.get("status"),
                      "passed": passed, "events": events}
            results.append(record)
            print(json.dumps({k:v for k,v in record.items() if k != "events"}), flush=True)
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/scenarios.json").write_text(json.dumps(results, indent=2))
    assert all(r["passed"] for r in results), "See artifacts/scenarios.json"


if __name__ == "__main__":
    main()
