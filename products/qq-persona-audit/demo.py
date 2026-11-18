#!/usr/bin/env python3
"""Demo for qq-persona-audit.

Builds two temp fixture personas (one healthy, one missing the singing
command mapping), runs audit.py on each, prints the tables, and cleans up.
Only creates its own temp files; never touches a real config directory.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

AUDIT = Path(__file__).resolve().parent / "audit.py"

PROMPT = "你是一个群友，说话短，口语化。\n直接回消息，不引用对方。\n被点歌时就唱歌。\n"
CONFIG = {
    "temperature": 0.85, "top_p": 0.9, "max_tokens": 512,
    "commands": {"!唱歌": "sing", "@小深 唱歌": "sing"},
    "quote_reply": False,
}
REPLIES = [
    {"role": "xiao-shen", "text": "来了来了，刚吃完夜宵", "quote": False},
    {"role": "xiao-shen", "text": "这个我也不知道，等会儿翻翻", "quote": False},
    {"role": "xiao-shen", "text": "好嘞，这就给你唱", "quote": False},
    {"role": "mei-xiao", "text": "今天过得还好吗？累了就早点休息。", "quote": False},
    {"role": "mei-xiao", "text": "我在呢，怎么啦？", "quote": False},
]


def write_fixture(root, config):
    root.mkdir(parents=True, exist_ok=True)
    (root / "prompt.txt").write_text(PROMPT, encoding="utf-8")
    (root / "config.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8")
    (root / "simulated_replies.json").write_text(
        json.dumps(REPLIES, ensure_ascii=False), encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory(prefix="qq-persona-audit-demo-") as tmp:
        base = Path(tmp)
        write_fixture(base / "healthy", CONFIG)
        broken = dict(CONFIG)
        broken["commands"] = {}
        write_fixture(base / "no-sing", broken)
        for name in ("healthy", "no-sing"):
            print(f"== {name} ==")
            result = subprocess.run(
                [sys.executable, str(AUDIT), str(base / name)],
                capture_output=True, text=True, timeout=60)
            print(result.stdout, end="")
            if result.returncode != 0:
                print(result.stderr, file=sys.stderr)
                return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
