"""Tests for qq-persona-audit audit.py.

Builds temp fixture personas (deleted afterwards) and runs audit.py
as a subprocess. Fixture personas use generic example text only.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

AUDIT = Path(__file__).resolve().parent.parent / "audit.py"

HEALTHY_PROMPT = "你是一个群友，说话短，口语化。\n直接回消息，不引用对方。\n被点歌时就唱歌。\n"
HEALTHY_CONFIG = {
    "temperature": 0.85, "top_p": 0.9, "max_tokens": 512,
    "commands": {"!唱歌": "sing", "@小深 唱歌": "sing"},
    "quote_reply": False,
}
HEALTHY_REPLIES = [
    {"role": "xiao-shen", "text": "来了来了，刚吃完夜宵", "quote": False},
    {"role": "xiao-shen", "text": "这个我也不知道，等会儿翻翻", "quote": False},
    {"role": "xiao-shen", "text": "好嘞，这就给你唱", "quote": False},
    {"role": "mei-xiao", "text": "今天过得还好吗？累了就早点休息。", "quote": False},
    {"role": "mei-xiao", "text": "我在呢，怎么啦？", "quote": False},
]


def write_fixture(root, prompt=HEALTHY_PROMPT, config=HEALTHY_CONFIG,
                  replies=HEALTHY_REPLIES):
    root.mkdir(parents=True, exist_ok=True)
    (root / "prompt.txt").write_text(prompt, encoding="utf-8")
    (root / "config.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8")
    (root / "simulated_replies.json").write_text(
        json.dumps(replies, ensure_ascii=False), encoding="utf-8")


def run_audit(target, *args):
    return subprocess.run(
        [sys.executable, str(AUDIT), str(target), *args],
        capture_output=True, text=True, timeout=60)


def run_json(target):
    result = run_audit(target, "--json")
    assert result.returncode == 0
    return json.loads(result.stdout)


def hash_tree(root):
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    base = tmp_path_factory.mktemp("qq-persona-audit")
    write_fixture(base / "healthy")
    write_fixture(
        base / "ai-cavity",
        prompt="你是一个群友，说话短，口语化。\n总的来说，我们是一家人。\n直接回消息，不引用对方。\n")
    replies = [dict(r) for r in HEALTHY_REPLIES]
    replies[0]["text"] = "来了来了。刚吃完夜宵。味道还不错。明天再去一次。"
    write_fixture(base / "long", replies=replies)
    replies = [dict(r) for r in HEALTHY_REPLIES]
    replies[1]["quote"] = True
    write_fixture(base / "quote", replies=replies)
    config = dict(HEALTHY_CONFIG)
    config["commands"] = {}
    write_fixture(base / "no-sing", config=config)
    config = dict(HEALTHY_CONFIG)
    config["temperature"] = 1.5
    write_fixture(base / "params", config=config)
    replies = [{"role": "mei-xiao",
                "text": "今天过得还好吗？累了就早点休息。记得多喝水。",
                "quote": False}]
    write_fixture(base / "meixiao", replies=replies)
    return base


def test_healthy_has_no_issues(root):
    data = run_json(root / "healthy")
    assert data["summary"] == {"checks": 6, "issues": 0, "unverified": 0}
    assert data["rows"] == []


def test_ai_cavity_reports_line_number(root):
    data = run_json(root / "ai-cavity")
    assert data["summary"]["issues"] == 1
    row = data["rows"][0]
    assert row["check"] == "AI 腔"
    assert row["location"] == "prompt.txt:2"
    assert "总的来说" in row["issue"]


def test_long_reply_reports_sentence_length(root):
    data = run_json(root / "long")
    assert data["summary"]["issues"] == 1
    assert data["rows"][0]["check"] == "碎话短句"
    assert data["rows"][0]["location"] == "模拟消息 #1"


def test_quoted_reply_reports_quote(root):
    data = run_json(root / "quote")
    assert data["summary"]["issues"] == 1
    assert data["rows"][0]["check"] == "quote 回复"
    assert data["rows"][0]["location"] == "模拟消息 #2"


def test_missing_singing_triggers_are_severe(root):
    data = run_json(root / "no-sing")
    assert data["summary"]["issues"] == 2
    assert all(r["check"] == "唱歌接线" and r["level"] == "严重"
               for r in data["rows"])


def test_out_of_range_temperature_reports_range(root):
    data = run_json(root / "params")
    assert data["summary"]["issues"] == 1
    row = data["rows"][0]
    assert row["check"] == "模型参数"
    assert "1.5" in row["issue"] and "0.7–1.0" in row["issue"]
    assert "0.7–1.0" in row["suggestion"]


def test_meixiao_three_sentences_reports_both_checks(root):
    data = run_json(root / "meixiao")
    assert data["summary"]["issues"] == 2
    assert {r["check"] for r in data["rows"]} == {"碎话短句", "美咲句长"}


def test_prompt_requiring_quote_is_reported(root):
    target = root / "quote-prompt"
    write_fixture(target, prompt="回消息时要引用回复，方便大家看清上下文。\n")
    data = run_json(target)
    assert data["summary"]["issues"] == 1
    assert data["rows"][0]["check"] == "quote 回复"
    assert data["rows"][0]["location"] == "prompt.txt:1"


def test_table_output_matches_json(root):
    result = run_audit(root / "no-sing")
    assert result.returncode == 0
    assert "检查 6 项，问题 2 条（未核实 0 条）" in result.stdout
    assert "唱歌接线" in result.stdout


def test_missing_config_reports_unverified(root):
    target = root / "bare"
    target.mkdir()
    (target / "prompt.txt").write_text(HEALTHY_PROMPT, encoding="utf-8")
    data = run_json(target)
    assert data["summary"]["issues"] == 0
    assert data["summary"]["unverified"] == 2
    assert {r["check"] for r in data["rows"]} == {"唱歌接线", "模型参数"}


def test_missing_prompt_reports_unverified(root):
    target = root / "no-prompt"
    target.mkdir()
    (target / "config.json").write_text(
        json.dumps(HEALTHY_CONFIG, ensure_ascii=False), encoding="utf-8")
    data = run_json(target)
    assert data["summary"]["unverified"] == 2
    assert {r["check"] for r in data["rows"]} == {"AI 腔", "quote 回复"}


def test_severity_ordering(root):
    data = run_json(root / "no-sing")
    rows = data["rows"]
    assert rows[0]["level"] == "严重"


def test_run_does_not_change_fixture(root):
    target = root / "healthy"
    before = hash_tree(target)
    result = run_audit(target)
    assert result.returncode == 0
    assert hash_tree(target) == before


def test_missing_directory_exits_2(root):
    result = run_audit(root / "does-not-exist")
    assert result.returncode == 2
