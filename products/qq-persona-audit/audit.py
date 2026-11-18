#!/usr/bin/env python3
"""QQ persona audit: read-only check of a LangBot / NapCat bot persona config.

Usage: python3 audit.py <config dir or fixture dir> [--json]

The directory is expected to contain:
  prompt.txt              persona prompt, one rule per line (required for
                          prompt checks; missing means those checks are
                          reported as unverified, never guessed)
  config.json             optional: {"temperature": ..., "top_p": ...,
                          "max_tokens": ..., "commands": {"!sing": "sing", ...},
                          "quote_reply": false}
  simulated_replies.json  optional: [{"role": "xiao-shen" | "mei-xiao" |
                          "generic", "text": "...", "quote": false}, ...]
                          When absent, five built-in simulated group messages
                          are used instead.

Exit code: 0 after a completed scan (even when issues are found),
2 when the directory does not exist or is not a directory.
Read-only: never writes, never sends a message, never connects to QQ.
"""

import json
import re
import sys
from pathlib import Path

# --- Rule word lists and thresholds (see checklist.md) ---------------------

AI_CAVITY_PHRASES = [
    "首先", "其次", "最后", "总的来说", "总而言之", "综上所述",
    "作为 AI", "作为人工智能", "作为一个 AI",
    "值得注意的是", "需要注意的是",
]
QUOTE_PROMPT_PHRASES = ["引用回复", "引用对方", "带引用回复", "quote 回复", "quote 回复"]
# A line that says NOT to quote ("不引用", "不要引用" ...) is a rule, not a
# violation; only a line that asks for quoting is reported.
QUOTE_NEGATIONS = ["不引用", "不要引用", "别引用", "不用引用", "禁止引用"]
# Singing triggers: each must map to the sing action in config.json.
SING_TRIGGERS = ["!唱歌", "@小深 唱歌"]
SING_ACTION = "sing"

PARAM_RANGES = {
    "temperature": (0.7, 1.0),
    "top_p": (0.8, 1.0),
    "max_tokens": (200, 1024),
}

# Sentence limits: (max sentences per message, max chars per sentence)
SENTENCE_LIMITS = {
    "xiao-shen": (3, 40),
    "mei-xiao": (2, 50),
    "generic": (3, 40),
}

BUILTIN_REPLIES = [
    {"role": "xiao-shen", "text": "来了来了，刚吃完夜宵", "quote": False},
    {"role": "xiao-shen", "text": "这个我也不知道，等会儿翻翻", "quote": False},
    {"role": "xiao-shen", "text": "好嘞，这就给你唱", "quote": False},
    {"role": "mei-xiao", "text": "今天过得还好吗？累了就早点休息。", "quote": False},
    {"role": "mei-xiao", "text": "我在呢，怎么啦？", "quote": False},
]

CHECKS = [
    "AI 腔", "碎话短句", "quote 回复", "美咲句长", "唱歌接线", "模型参数",
]

# Severity: 0 highest. 唱歌接线 and 模型参数 first, then AI 腔 and quote,
# then sentence length, then 未核实.
SEVERITY = {
    "唱歌接线": 0, "模型参数": 0,
    "AI 腔": 1, "quote 回复": 1,
    "碎话短句": 2, "美咲句长": 2,
}
LEVEL_NAME = {0: "严重", 1: "一般", 2: "轻微", 3: "未核实"}


def split_sentences(text):
    return [s for s in re.split(r"[。！？；\n]+", text) if s.strip()]


def check_ai_cavity(prompt_lines, replies):
    rows = []
    for i, line in enumerate(prompt_lines, 1):
        for phrase in AI_CAVITY_PHRASES:
            if phrase in line:
                rows.append({
                    "check": "AI 腔", "level": LEVEL_NAME[1],
                    "location": f"prompt.txt:{i}",
                    "issue": f"提示词出现书面化表达“{phrase}”。",
                    "suggestion": f"把 prompt.txt 第 {i} 行改成一句口语短句，删掉“{phrase}”再说事。",
                })
    for n, reply in enumerate(replies, 1):
        text = reply.get("text", "")
        for phrase in AI_CAVITY_PHRASES:
            if phrase in text:
                rows.append({
                    "check": "AI 腔", "level": LEVEL_NAME[1],
                    "location": f"模拟消息 #{n}",
                    "issue": f"模拟回复出现书面化表达“{phrase}”。",
                    "suggestion": f"把这句改成口语短句，删掉“{phrase}”再说事。",
                })
        for line in text.splitlines():
            if re.match(r"\s*(\d+[.、]|- |• )", line):
                rows.append({
                    "check": "AI 腔", "level": LEVEL_NAME[1],
                    "location": f"模拟消息 #{n}",
                    "issue": "模拟回复出现列表式表达。",
                    "suggestion": "别列条目，挑最重要的一句口语说出来就行。",
                })
                break
    return rows


def check_sentence_length(replies):
    rows = []
    for n, reply in enumerate(replies, 1):
        role = reply.get("role", "generic")
        if role not in SENTENCE_LIMITS:
            role = "generic"
        max_sentences, max_chars = SENTENCE_LIMITS[role]
        text = reply.get("text", "")
        sentences = split_sentences(text)
        if len(sentences) > max_sentences:
            rows.append({
                "check": "碎话短句", "level": LEVEL_NAME[2],
                "location": f"模拟消息 #{n}",
                "issue": f"模拟回复共 {len(sentences)} 句，超过 {role} 上限 {max_sentences} 句。",
                "suggestion": "只留最关键的一两句，其余删掉或拆成下一条再说。",
            })
        for s in sentences:
            if len(s) > max_chars:
                rows.append({
                    "check": "碎话短句", "level": LEVEL_NAME[2],
                    "location": f"模拟消息 #{n}",
                    "issue": f"模拟回复单句 {len(s)} 字，超过 {role} 上限 {max_chars} 字。",
                    "suggestion": "把这句从中间断开，改成两句短的。",
                })
                break
    return rows


def check_quote(prompt_lines, replies, config):
    rows = []
    for i, line in enumerate(prompt_lines, 1):
        if any(neg in line for neg in QUOTE_NEGATIONS):
            continue
        for phrase in QUOTE_PROMPT_PHRASES:
            if phrase in line:
                rows.append({
                    "check": "quote 回复", "level": LEVEL_NAME[1],
                    "location": f"prompt.txt:{i}",
                    "issue": f"提示词要求引用回复（“{phrase}”），与不 quote 回复的约定冲突。",
                    "suggestion": f"把 prompt.txt 第 {i} 行改成“直接回，不引用对方消息”。",
                })
    if isinstance(config, dict) and config.get("quote_reply") is True:
        rows.append({
            "check": "quote 回复", "level": LEVEL_NAME[1],
            "location": "config.json:quote_reply",
            "issue": "配置里 quote_reply 为 true，要求引用回复。",
            "suggestion": "把 config.json 里的 quote_reply 改成 false。",
        })
    for n, reply in enumerate(replies, 1):
        if reply.get("quote") is True:
            rows.append({
                "check": "quote 回复", "level": LEVEL_NAME[1],
                "location": f"模拟消息 #{n}",
                "issue": "模拟消息带引用格式。",
                "suggestion": "这条直接回，别带引用。",
            })
    return rows


def check_meixiao_length(replies):
    rows = []
    for n, reply in enumerate(replies, 1):
        if reply.get("role") != "mei-xiao":
            continue
        text = reply.get("text", "")
        sentences = split_sentences(text)
        max_sentences, max_chars = SENTENCE_LIMITS["mei-xiao"]
        if len(sentences) > max_sentences:
            rows.append({
                "check": "美咲句长", "level": LEVEL_NAME[2],
                "location": f"模拟消息 #{n}",
                "issue": f"美咲式回复共 {len(sentences)} 句，超过 2 句上限。",
                "suggestion": "只留一到两句，多的那句删掉或放到下一条。",
            })
        for s in sentences:
            if len(s) > max_chars:
                rows.append({
                    "check": "美咲句长", "level": LEVEL_NAME[2],
                    "location": f"模拟消息 #{n}",
                    "issue": f"美咲式回复单句 {len(s)} 字，超过 {max_chars} 字上限。",
                    "suggestion": "把这句断成两句短的。",
                })
                break
    return rows


def check_singing(config):
    rows = []
    if not isinstance(config, dict):
        rows.append({
            "check": "唱歌接线", "level": LEVEL_NAME[3],
            "location": "config.json",
            "issue": "config.json 缺失或解析失败，唱歌接线未核实。",
            "suggestion": "确认 config.json 存在且是合法 JSON，再跑一遍。",
        })
        return rows
    commands = config.get("commands")
    if not isinstance(commands, dict):
        rows.append({
            "check": "唱歌接线", "level": LEVEL_NAME[3],
            "location": "config.json:commands",
            "issue": "config.json 里没有 commands 映射，唱歌接线未核实。",
            "suggestion": "在 config.json 里补上 commands 映射，再跑一遍。",
        })
        return rows
    for trigger in SING_TRIGGERS:
        if trigger not in commands:
            rows.append({
                "check": "唱歌接线", "level": LEVEL_NAME[0],
                "location": "config.json:commands",
                "issue": f"触发词“{trigger}”缺失，没有映射到唱歌动作。",
                "suggestion": f"在 commands 里加上“{trigger}”: \"{SING_ACTION}”。",
            })
        else:
            action = str(commands[trigger])
            if SING_ACTION not in action.lower() and "唱歌" not in action:
                rows.append({
                    "check": "唱歌接线", "level": LEVEL_NAME[0],
                    "location": "config.json:commands",
                    "issue": f"触发词“{trigger}”映射到了“{action}”，不是唱歌动作。",
                    "suggestion": f"把“{trigger}”的映射改成 \"{SING_ACTION}\"。",
                })
    return rows


def check_params(config):
    rows = []
    if not isinstance(config, dict):
        rows.append({
            "check": "模型参数", "level": LEVEL_NAME[3],
            "location": "config.json",
            "issue": "config.json 缺失或解析失败，模型参数未核实。",
            "suggestion": "确认 config.json 存在且是合法 JSON，再跑一遍。",
        })
        return rows
    for name, (low, high) in PARAM_RANGES.items():
        value = config.get(name)
        if value is None:
            rows.append({
                "check": "模型参数", "level": LEVEL_NAME[3],
                "location": f"config.json:{name}",
                "issue": f"{name} 缺失，未核实。",
                "suggestion": f"在 config.json 里补上 {name}，建议范围 {low}–{high}。",
            })
        elif not isinstance(value, (int, float)) or not low <= value <= high:
            rows.append({
                "check": "模型参数", "level": LEVEL_NAME[0],
                "location": f"config.json:{name}",
                "issue": f"{name} 为 {value}，超出建议范围 {low}–{high}。",
                "suggestion": f"把 {name} 改到 {low}–{high} 之间，例如 {(low + high) / 2}。",
            })
    return rows


def load_config(root):
    prompt_path = root / "prompt.txt"
    prompt_lines = []
    prompt_missing = False
    if prompt_path.is_file():
        prompt_lines = prompt_path.read_text(encoding="utf-8").splitlines()
    else:
        prompt_missing = True

    config = None
    config_path = root / "config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            config = None
    if not isinstance(config, dict):
        config = None

    replies = list(BUILTIN_REPLIES)
    replies_path = root / "simulated_replies.json"
    if replies_path.is_file():
        try:
            loaded = json.loads(replies_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list) and loaded:
                replies = loaded
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return prompt_lines, prompt_missing, config, replies


def audit(root):
    prompt_lines, prompt_missing, config, replies = load_config(root)
    rows = []
    if prompt_missing:
        rows.append({
            "check": "AI 腔", "level": LEVEL_NAME[3],
            "location": "prompt.txt",
            "issue": "prompt.txt 缺失，提示词检查未核实。",
            "suggestion": "确认 prompt.txt 存在，再跑一遍。",
        })
        rows.append({
            "check": "quote 回复", "level": LEVEL_NAME[3],
            "location": "prompt.txt",
            "issue": "prompt.txt 缺失，提示词检查未核实。",
            "suggestion": "确认 prompt.txt 存在，再跑一遍。",
        })
    else:
        rows += check_ai_cavity(prompt_lines, replies)
        rows += check_quote(prompt_lines, replies, config)
    rows += check_sentence_length(replies)
    rows += check_meixiao_length(replies)
    rows += check_singing(config)
    rows += check_params(config)
    rows.sort(key=lambda r: (SEVERITY[r["check"]] if r["level"] != "未核实" else 3,
                             r["check"], r["location"]))
    issues = sum(1 for r in rows if r["level"] != "未核实")
    unverified = sum(1 for r in rows if r["level"] == "未核实")
    summary = {
        "checks": len(CHECKS),
        "issues": issues,
        "unverified": unverified,
    }
    return rows, summary


def print_table(rows, summary):
    headers = ["检查项", "级别", "位置", "问题描述", "改一句的建议"]
    keys = ["check", "level", "location", "issue", "suggestion"]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, key in enumerate(keys):
            widths[i] = max(widths[i], len(str(row[key])))
    def fmt(values):
        return "| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(values)) + " |"
    print(fmt(headers))
    print(fmt(["-" * w for w in widths]))
    for row in rows:
        print(fmt([row[k] for k in keys]))
    print()
    print(f"检查 {summary['checks']} 项，问题 {summary['issues']} 条"
          f"（未核实 {summary['unverified']} 条）")


def main(argv):
    if len(argv) < 2 or len(argv) > 3 or (len(argv) == 3 and argv[2] != "--json"):
        print("用法：python3 audit.py <配置目录或 fixture 目录> [--json]", file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"目录不存在或不是目录：{root}", file=sys.stderr)
        return 2
    rows, summary = audit(root)
    if len(argv) == 3:
        print(json.dumps({"rows": rows, "summary": summary},
                         ensure_ascii=False, indent=2))
    else:
        print_table(rows, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
