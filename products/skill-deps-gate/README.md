# skill-deps-gate

skill-deps-gate 根据 skill 的 frontmatter 声明，对照一份离线项目快照，检查工具和服务器依赖是否满足。它只读取命令行给出的 skill 目录和快照文件，不执行 skill 正文，不探测 PATH，也不连接真实 MCP。本项目只支持下面约定的子集，并不是对完整规范的全面支持。

## 安装

从仓库根目录执行下面的命令，进入 `products/skill-deps-gate` 后创建并激活虚拟环境，再安装运行依赖：

```bash
cd products/skill-deps-gate
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

运行依赖写在 `requirements.txt`，当前是 PyYAML 6.0.1。程序运行时不安装软件，也不访问网络。

离线安装时，把轮子文件放到一个目录中，并把下面命令里的 `"./wheels"` 换成该目录的实际路径：

```bash
python3 -m pip install --no-index --find-links "./wheels" -r requirements.txt
```

测试依赖写在 `requirements-dev.txt`，包含 pytest 和同一个 PyYAML。需要跑测试时，在同一产品目录和已激活的虚拟环境中执行：

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

## 检查单个 skill

完成安装后，继续在当前产品目录中执行。`--skill` 可以重复。`--snapshot` 只能给一次。

下面的 skill 名称、工具名和服务器名都是虚构样例，只用来说明用法。正例：

```bash
python3 -m skill_deps_gate --skill fixtures/skill-any --snapshot fixtures/snapshots/any-on-docs.json
```

该 skill 的 frontmatter 如下：

```yaml
---
name: fixture-any
description: Fictional skill for the any group.
dependencies:
  tools:
    any:
      - search
      - fetch
requires-mcp-servers:
  - docs
---
```

它声明 `dependencies.tools.any` 为 `search` 和 `fetch`，并在顶层用 `requires-mcp-servers` 点名一台服务器 `docs`。这份样例没有 `tools.all`。在对应快照里，`search` 在被点名的 `docs` 上，`fetch` 只在另一台服务器上。退出码是 0。矩阵里 `search` 满足，`fetch` 缺失，`docs` 满足；`any` 已经有一项满足。

反例：

```bash
python3 -m skill_deps_gate --skill fixtures/skill-any --snapshot fixtures/snapshots/any-on-other.json
```

`docs` 存在，`search` 和 `fetch` 都只在 `other` 上。退出码是 1，标准错误是：

```text
unsatisfied: dependencies.tools.any
```

## 检查多个目录

若作为 `--skill` 给出的目录本身是普通目录，并且里面有普通文件 `SKILL.md`，就把它当作一个 skill，不再扫描子目录。若该目录没有 `SKILL.md`，再向下查找。多个根目录按命令行顺序输出，同一根目录里的 skill 按路径排序。同名 skill 不合并，靠路径区分。

成功入口：

```bash
python3 -m skill_deps_gate --skill fixtures/roots/ok --snapshot fixtures/snapshots/scan-ok.json
python3 -m skill_deps_gate --skill fixtures/roots/ok --skill fixtures/roots/extra --snapshot fixtures/snapshots/scan-ok.json
```

这两条命令的退出码是 0。

失败入口是同一个扫描根里的两个 skill。`bad` 声明了快照里没有的 `absenttool`，`good` 声明的 `search` 在 `docs` 上：

```bash
python3 -m skill_deps_gate --skill fixtures/roots/mixed --snapshot fixtures/snapshots/scan-ok.json
```

退出码是 1。标准错误只有一行：

```text
unsatisfied: fixtures/roots/mixed/bad: absenttool
```

`good` 的满足行仍保持满足。缺依赖不会把已经满足的行改成未判定。

## 快照格式

程序不接受原生 `tools/list`。那份 JSON 没有可靠的服务器身份，不能从工具名、描述或前缀推断服务器。这是本项目的离线封装，不是一次真实 MCP 连接的记录。错误提示里会给出下面这种封装例子：

```json
{
  "skill_deps_gate_snapshot": 1,
  "servers": [
    {
      "server": "docs",
      "tools": [
        {
          "name": "search"
        }
      ]
    }
  ]
}
```

版本必须是 JSON 整数 1。`1.0` 和 `true` 都会被拒绝。每个服务器都要有非空字符串 `server`，每个工具对象只能有字符串 `name`。重复的 JSON 键会被拒绝。作为 `--snapshot` 给出的路径按参数路径段检查符号链接。快照必须是普通文件，非普通文件会在读取前被拒绝。路径检查的细节见下面的「路径和符号链接」。

## 满足条件

[agentskills issue 485](https://github.com/agentskills/agentskills/issues/485) 提出用 `all` 表示全部满足、用 `any` 表示至少一项满足，并把裸列表当作 `all` 的简写。跨服务器身份在该草案中尚未确定。本项目还接受顶层字段 `requires-mcp-servers`，它不是草案正文里的字段。本项目只支持这里列出的约定子集，并不是对完整规范的全面支持。

1. `all` 的每一项都要满足。`any` 至少一项要满足。两组同时存在时，两组都要满足。
2. 恰好点名一台服务器时，工具只在那台上做全字匹配。这是本项目的限定，不是草案保证的绑定。
3. 没有服务器声明时，工具名在全部已标识服务器的集合里查找。
4. 多个不同服务器再加 `all` 或 `any` 时会拒绝，不猜交叉积。把同一个服务器名重复写多次，不会因此被当成多个不同服务器。
5. 该草案把裸列表当作 `all` 的简写。本项目把裸列表按输入错误处理，退出码是 2。要声明工具依赖，需使用显式的 `all` 或 `any`。
6. 没有依赖声明时，退出码是 1，并写明拒绝视为通过。
7. frontmatter 只在未缩进、且整行正好是 `---` 时结束。描述块里缩进的 `---` 不会截掉后面的声明。

只有服务器声明时，逐个检查声明的服务器是否出现在快照里。名称匹配区分大小写，工具名须完整一致，不以子串或前缀命中，也不把 `server/tool` 拆开解释。

顶层可以出现 `license`、`compatibility`、`metadata` 和 `allowed-tools`。门禁允许这些字段出现，但不解释它们的含义。这不是完整规范支持。`name`、`description`、`dependencies` 和 `requires-mcp-servers` 是正常字段，不会被当成未知字段拒绝。除这些正常字段和上述四个元数据字段以外，未知的顶层字段以及未知的依赖组合都会被拒绝，退出码是 1。

## 输出和退出码

标准输出的矩阵第一行是 `技能`、`路径`、`依赖`、`种类`、`状态`。同一声明里重复出现的依赖按声明重复各占一行，不自动去重。

| 退出码 | 含义 |
|---|---|
| 0 | 需要满足的声明都满足 |
| 1 | 依赖缺失，或出现尚不支持的字段或依赖组合 |
| 2 | 输入错误 |

同一轮里只要出现输入错误，退出码就是 2。这时原本满足的行会改成未判定。缺失行仍可能显示为缺失，标准错误里除了 `error:` 之外，也仍可能出现 `unsatisfied:`。这些残留信息不作为该轮有效的依赖结论。依赖缺失和输入错误同时出现时，也取 2。只有依赖缺失、没有输入错误时，退出码是 1，已满足的行保持满足。没有依赖声明，以及未知的顶层字段或未知的依赖组合，退出码是 1。`dependencies: null` 属于输入错误，退出码是 2，见「限制」。

标准错误以 `error:`、`unsatisfied:` 或 `unsupported:` 开头。失败时不打印 Python traceback。

## 路径和符号链接

对 `--skill` 和 `--snapshot`，程序按参数字符串里的路径段逐段检查，不先把链接解析掉。检查范围包括祖先段，以及先经过链接再使用 `..` 回到真实目录的写法。最后一段无论是指向真实目录的符号链接，还是断链，都会被拒绝。祖先段是符号链接，或先经过符号链接再使用 `..` 回到真实目录，同样会被拒绝。这些情况的退出码是 2，标准输出不显示满足。`--snapshot` 若指向文件符号链接，标准输出为空，标准错误是 `error: 快照路径不允许符号链接`。普通目录里的 `SKILL.md` 自身若是文件符号链接，同样退出码 2。一次调用里同时给出普通已满足的 skill 和带链接段的参数时，整轮仍是 2，已满足的行改成未判定。

这项检查看的是参数里的路径段，并不承诺检查进程怎样进入当前工作目录。当前工作目录即使经由链接进入，只要参数字符串里没有链接段，仍按普通路径处理。

若作为 `--skill` 给出的根目录本身不是链接，向下扫描时会拒绝指向真实目录的子目录链接，以及名为 `SKILL.md` 的文件链接，包括断链，并且不读取链接目标。整轮退出码是 2。同一根里已经发现的合法 skill 会保留在矩阵中，原本满足的行改为未判定。名为 `SKILL.md` 以外的普通文件链接，以及其他断链子项，会被忽略，不会仅因此把整轮判为输入错误。不要把扫描策略理解成目录树里出现任何符号链接都会以退出码 2 拒绝。

## 限制

程序不探测 PATH，不安装软件，不编排依赖，不做安全扫描，不联网，不调用工具，也不执行 skill 正文。它不连接真实 MCP。检查只使用命令行给出的目录和快照。

单个输入超过 1048576 字节（1 MiB）会被拒绝。`SKILL.md` 和快照必须是普通文件。FIFO 在打开前就会被拒绝。不可读目录属于输入错误。

多个不同服务器再加 `all` 或 `any` 时会被拒绝，不猜交叉积。多个服务器和工具如何绑定，语义尚未确定。

`dependencies.tools` 写成 `tools:` 或 `tools: null` 时，退出码是 1。`dependencies: null` 的退出码是 2。

本项目只支持这里约定的子集，并不是对完整规范的全面支持。
