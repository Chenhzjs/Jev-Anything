#!/usr/bin/env python3
"""Minimal live smoke test for the configured Jev provider."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jev_anything import JevClient, JevError


def load_dotenv() -> None:
    env_path = Path(__file__).parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    load_dotenv()
    try:
        answers = JevClient().decide(
            state={"dialog": "用户表达了稳定的长期偏好"},
            questions={
                "remember": {
                    "type": "noul",
                    "instructions": "这段内容是否值得长期记忆？",
                    "criteria": {
                        "true": "包含稳定偏好或长期信息",
                        "false": "仅包含一次性任务或普通问答",
                    },
                }
            },
        )
    except JevError as exc:
        print(f"Jev smoke test failed: {exc}", file=sys.stderr)
        return 1
    print(answers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
