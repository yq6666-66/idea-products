# md-dead-links

扫仓库里的 Markdown：本地链接查文件是否存在，外链做 HEAD（失败再 GET），超时单独标出。只输出断链表，不改文件。

成熟替代：若你已装 [lychee](https://github.com/lycheeverse/lychee)，可直接 `lychee .`，覆盖面更大。本 MVP 是零依赖小脚本。

## 跑法

```bash
python3 check.py /path/to/repo
python3 check.py /path/to/repo --warn-only  # 只出报告、exit 0
```

## 演示

`demo/` 里有两份 Markdown：`./ok.md` 是好的本地链接，`./missing.md` 不存在，外链指向保留域名 `example.invalid`（解析失败，当成断链）。

在本目录执行：

```bash
python3 check.py demo
python3 check.py demo --warn-only
```

有断链时默认 exit 1。`--warn-only` 打同一份报告，exit 0。断链两行类似（前面的 `generated_at` 会变）：

```
- [dead] README.md: ./missing.md (missing-file)
- [dead] README.md: https://example.invalid/md-dead-links-demo (URLError)
```

## 自测

```bash
cd products/md-dead-links
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

