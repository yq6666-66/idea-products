# mcp-tool-drift

只读 CLI：汇总本机多客户端 MCP 配置，对每个 server 只做 `initialize` + `tools/list` 快照，再和上次快照做本地 diff（新增 / 消失 / schema 破坏性变更）。

和 health check 的三点差别：

1. 聚合多客户端配置（Cursor、Claude Desktop，路径可改），不是探活单个进程。
2. 快照只有 `initialize` + `tools/list`，零业务副作用（不发 `tools/call`，不读写资源，不改用户配置）。
3. 本地 diff 报 `added` / `removed` / `breaking` / `unchanged`，不是 up/down。

没有直接等价物。抓包、token 计量、注入检测、进程探活都不是这件事。

`stdio` 传输会拉起配置里的 `command`。演示和测试只用自带假配置或 `demo/fake_mcp.py`，不访问网络，也不连真实 MCP。

## 跑法

在 `products/mcp-tool-drift` 下：

```bash
python3 cli.py --help

python3 cli.py offline --config demo/cursor-mcp.good.json
python3 cli.py offline --config demo/cursor-mcp.bad.json

python3 cli.py discover --root demo/home

python3 cli.py online --config demo/cursor-mcp.good.json \
  --transport mock --mock-tools demo/mock-tools.json --timeout 5 --out /tmp/mcp-snap.json

python3 cli.py online --config demo/stdio-mcp.json \
  --transport stdio --timeout 5 --out /tmp/mcp-stdio.json

python3 cli.py diff --before demo/snapshot-a.json --after demo/snapshot-b.json
python3 cli.py diff --before demo/snapshot-a.json --after demo/snapshot-b.json --warn-only

python3 demo/run.py
```

`discover` 不带 `--root` 时按当前用户主目录找配置，只读，不会改文件。未知或坏掉的文件打印 `warn:` 后跳过。默认路径（每个客户端命中第一个能解析的）：

| 客户端 | 相对主目录 |
|---|---|
| `cursor` | `.cursor/mcp.json` |
| `claude-desktop` | `Library/Application Support/Claude/claude_desktop_config.json`，然后 `.config/Claude/claude_desktop_config.json`，然后 `AppData/Roaming/Claude/claude_desktop_config.json` |

换路径：`--path cursor=/somewhere/mcp.json`（可重复）。这个列表会替换该客户端的默认路径。

`offline` 只打印 `mcpServers` 里的名字，一行一个，排序。不打印 `command` / `args` / `env`。坏 JSON 或结构不对：退出码 2。

`discover` 的一行是 `client`、server、`command`、`args`、`url`。`env` 的值一律写成 `***`。

`online --transport mock` 不启动子进程，工具列表来自 `--mock-tools`（server 名 → 工具数组）。一个 server 时快照是「工具名 → `{schema_hash, description_hash?}`」。多个 server 时外包一层 `servers`。`schema_hash` 是规范化 `inputSchema`（键排序、紧凑 JSON）的 SHA-256。只改 `description_hash` 不算 breaking。`--transport stdio` 会执行配置中的命令，并且只发送 `initialize`、`notifications/initialized`、`tools/list`。有 `url` 且没有 `command` 时默认走 `http`。

退出码：offline / discover 成功，以及 diff 里没有 `removed` 和 `breaking` → 0。有 `removed` 或 `breaking` → 1。配置或快照无法解析、传输失败或超时 → 2。`--warn-only` 在发现 drift 时仍为 0。仅 `added` 仍为 0。

夹具 diff：`list_tools` 新增，`legacy_ping` 消失，`search` 的 schema 哈希变化，`echo` 不变。

## 自测

```bash
cd products/mcp-tool-drift
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```
