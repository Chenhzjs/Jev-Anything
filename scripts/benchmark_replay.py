"""Replay recorded GUI2TUI observations through Jev and an exact-label baseline."""
import json
import time
from pathlib import Path
from test_jev import load_dotenv
from jev_anything import JevClient

load_dotenv()
records = json.loads(Path("artifacts/acceptance.json").read_text())
goals = {"success": ("Enable dark mode", "c-theme"), "settings": ("Open settings", "c-settings"), "abstain": ("Transfer money to a bank account", "abstain"), "unknown": ("Request background refresh", "c-refresh")}
results = []
client = JevClient()
for record in records:
    if record["provider"] != "rule" or record["case"] not in goals:
        continue
    observation = next(e["observation"] for e in record["events"] if e["kind"] == "observe")
    question = next(e["questions"] for e in record["events"] if e["kind"] == "jev_request")
    goal, expected = goals[record["case"]]
    for provider in ("rule", "jev"):
        start = time.monotonic()
        error = None
        metadata = {}
        try:
            if provider == "jev":
                answer = client.decide(state={"goal": goal, "observation": observation}, questions=question)["action"]["choice"]
                metadata = client.metadata
            else:
                answer = next((c["id"] for c in observation["candidates"] if c["label"].lower() in goal.lower()), "abstain")
        except Exception as exc:
            answer, error = None, str(exc)
        results.append({"case": record["case"], "provider": provider, "generation": observation["generation"], "expected": expected, "selected": answer, "correct": answer == expected, "latency_ms": round((time.monotonic()-start)*1000), "error": error, **metadata})
summary = {p: {"correct": sum(r["correct"] for r in results if r["provider"] == p), "total": sum(r["provider"] == p for r in results)} for p in ("rule", "jev")}
Path("artifacts/benchmark.json").write_text(json.dumps({"track": "development_fixture_only", "results": results, "summary": summary}, indent=2))
print(json.dumps(summary))
assert all(r["correct"] for r in results)
