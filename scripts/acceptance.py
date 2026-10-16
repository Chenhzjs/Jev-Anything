"""Exercise the running Docker workbench and save complete live traces."""
import json
import time
from pathlib import Path
import requests

BASE = "http://localhost:8787"


def wait_idle():
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        if not requests.get(BASE + "/api/frame", timeout=5).json()["busy"]:
            return
        time.sleep(0.2)
    raise AssertionError("Workbench timeout")


def main():
    results = []
    for provider in ("rule", "jev"):
        for name, goal, scenario, expected in (
            ("success", "Enable dark mode", "normal", "confirmed"),
            ("settings", "Open settings", "normal", "confirmed"),
            ("abstain", "Transfer money to a bank account", "normal", "abstained"),
            ("stale", "Enable dark mode", "stale", "rejected"),
            ("unknown", "Request background refresh", "normal", "unknown"),
        ):
            wait_idle()
            requests.post(BASE + "/api/reset", timeout=5).raise_for_status()
            wait_idle()
            start = len(requests.get(BASE + "/api/events", timeout=5).json())
            response = requests.post(BASE + "/api/run", params={"goal": goal, "provider": provider, "scenario": scenario}, timeout=5)
            response.raise_for_status()
            conflict = requests.post(BASE + "/api/reset", timeout=5)
            assert conflict.status_code == 409
            # Observe an unfinished run, not a fabricated post-completion playback.
            time.sleep(0.3)
            partial = requests.get(BASE + "/api/events", timeout=5).json()[start:]
            assert partial and not any(e["kind"] == "outcome" for e in partial)
            wait_idle()
            events = requests.get(BASE + "/api/events", timeout=5).json()[start:]
            outcome = events[-1].get("outcome", {})
            decision = next((e["decision"] for e in events if e["kind"] == "decision"), {})
            result = {"case": name, "provider": provider, "expected": expected, "actual": outcome.get("status"), "passed": outcome.get("status") == expected, "decision": decision, "events": events}
            results.append(result)
            print(json.dumps({k:v for k,v in result.items() if k not in {"events", "decision"}}), flush=True)
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    (output / "acceptance.json").write_text(json.dumps(results, indent=2))
    assert all(r["passed"] for r in results), "Acceptance failures; see artifacts/acceptance.json"


if __name__ == "__main__":
    main()
