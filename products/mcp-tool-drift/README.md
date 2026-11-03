# mcp-tool-drift

只读 CLI：汇总本机多客户端 MCP 配置，对每个 server 只做 `initialize` + `tools/list` 快照，再和上次快照做本地 diff（新增 / 消失 / schema 破坏性变更）。

和 health check 的三点差别：

1. 聚合多客户端配置（Cursor、Claude Desktop 等已知路径），不是探活单个进程。
2. 快照只有 `initialize` + `tools/list`，零业务副作用（不发 `tools/call`，不读写资源）。
3. 本地 diff 报 `added` / `removed` / `breaking`，不是 up/down。

本目录是 **P1 样本**。只解析自带假配置、只比较自带快照。不发现本机配置，不启动 MCP server，不调用任何 tool。正式 MVP 以后再做。

## 样本

在 `products/mcp-tool-drift` 下：

```bash
python3 cli.py --help

python3 cli.py offline --config demo/cursor-mcp.good.json
python3 cli.py offline --config demo/cursor-mcp.bad.json

python3 cli.py diff --before demo/snapshot-a.json --after demo/snapshot-b.json
python3 cli.py diff --before demo/snapshot-a.json --after demo/snapshot-b.json --warn-only
```

`offline` 只读 Cursor 风格 JSON 里的 `mcpServers` 名称，一行一个，按名字排序。不打印 `command` / `args` / `env`。坏 JSON 或结构不对：退出码 2。

快照是「工具名 → `{schema_hash, description_hash?}`」。`breaking` 表示同名工具的 `schema_hash` 变了。只改 `description_hash` 不算 breaking。

退出码：offline 成功、以及 diff 里没有 `removed` 和 `breaking` → 0。有 `removed` 或 `breaking` → 1。配置或快照无法解析 → 2。`--warn-only` 在发现 drift 时仍为 0。仅 `added` 仍为 0。

夹具 diff：`list_tools` 新增，`legacy_ping` 消失，`search` 的 schema 哈希变化，`echo` 不变。

## 自测

```bash
cd products/mcp-tool-drift
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```
