# skill-deps-gate

实现状态：本目录已有只读 MVP。未经独立 QA，不是发布，也不表示审查已通过。范围见 [SCOPE.md](./SCOPE.md)。

日期：2026-11-12（北京时间）。2026-11-10 的竞品结论仍按当时的调研保留。2026-11-12 只额外阅读了 agentskills issue 485 的公开页面，用来核对字段形状。

## 一句话

在加载 Skill 前，对照当前环境里的 MCP `tools/list` 检查 `SKILL.md` 声明的工具依赖。后续可以把 PATH 命令探测作为可选项加上。缺什么就立刻失败，避免 agent 跑到一半才报错，或幻觉出当前环境没有的能力。

## 痛点

Skill 正文常默认某个 MCP 工具或命令行工具一定存在。宿主仍会把这份 Skill 放进上下文，于是执行到一半才报错，或者编造出当前会话里并不存在的能力。官方草案 [agentskills issue 485](https://github.com/agentskills/agentskills/issues/485) 希望增加可机读的 `dependencies.tools.all` 与 `dependencies.tools.any`。2026-11-10 调研时，该草案尚未定稿。2026-11-12 阅读公开页面时，页面显示该议题为 open，最近更新时间是 2026-11-01。这次阅读只核对形状，不是竞品复核，也不表示草案已被接受。

## 目标用户

同时安装多套 Skill 和多个 MCP 的 Cursor、Claude Code、Codex 个人开发者。

## 相邻但不同的轴

1. 本库已有的 [mcp-tool-drift](../mcp-tool-drift/) 对照的是 MCP 工具表相对上次快照有没有漂移。本点子对照的是 Skill 声明的依赖是否被当前工具表满足。
2. agent-perm-matrix 讨论的是权限矩阵。本点子不判断权限是否允许，只判断声明的依赖是否出现在当前工具表里。

## 2026-11-10 调研时的竞品结论

下表和后面的交叉结论都来自 2026-11-10 调研。收录本文时只确认这些 URL 仍可打开，不宣称在 2026-11-12 重新验证了草案状态或竞品覆盖范围。

| 方向 | 代表 | 2026-11-10 调研时是否覆盖本点子 |
|---|---|---|
| Skill 多客户端移植检查 | [xyiqq/skilldoctor](https://github.com/xyiqq/skilldoctor) 的 `compat` 与 `ci` | 否。它检查格式和客户端可移植性，不检查运行时工具是否存在。 |
| 把 Skill 暴露成 MCP | [mrsimpson/agentskills-mcp](https://github.com/mrsimpson/agentskills-mcp)（调研时约 5 星） | 否。它暴露 Skill，不对照会话 `tools/list` 做门禁。 |
| 规范草案 | [agentskills issue 485](https://github.com/agentskills/agentskills/issues/485)（2026-11-10 调研时仍为 open） | 只有声明形状，没有本地门禁实现。 |
| 内容漂移、schema 漂移、权限矩阵 | skill-source-drift、本库的 mcp-tool-drift、agent-perm-matrix | 相邻但不同轴。本点子只回答依赖是否满足。 |

2026-11-10 用 DeepSeek-flash 做过一次交叉阅读，结论是值得做。当时对竞品的判断是部分覆盖，信号为中。理由是痛点真实，可以做成静态门禁，后续 MVP 保持只读，并用退出码表达结果。该草案在调研时尚未定稿，后续实现要做解析适配层，不能绑死在单一字段名上。这次收录没有重跑该交叉阅读。

## 草案形状与本项目约定

2026-11-12 读到的草案形状是：`dependencies.tools.all` 要求每一项都可用，`dependencies.tools.any` 要求至少一项可用。草案还把裸列表当作 `all` 的简写，并把判定说成偏软：名字解析失败不应让 frontmatter 本身无效。草案写明跨服务器的工具身份尚未决定。页面上的一条评论提到 `server/tool` 这种写法，它不是草案正文里的字段。

本项目的约定不同于草案保证的内容。

1. `requires-mcp-servers` 是本项目额外接受的声明，不是该草案正文里的字段。
2. 恰好点名一台服务器时，`all` 和 `any` 都只在那一台服务器的工具名上做全字匹配。这是本项目的单服务器限定，不是草案保证的绑定。
3. 没有服务器声明时，工具名在快照里全部已标识服务器的工具集合中查找。
4. 多个不同服务器再加工具声明时，关系并不明确，直接拒绝，不猜交叉积，也不解析 `server/tool` 前缀。
5. 裸列表不按 `all` 放行，格式不对就作为输入错误。
6. 本项目用退出码做硬门禁。依赖缺失或尚不支持是 1，输入错误是 2。这比草案里的软判定更严。
7. 快照必须自带服务器身份。原生 `tools/list` 不能证明服务器身份时会拒绝，并给出封装例子。实现没有连接真实 MCP。

## 明确不做

下列方向在 2026-11-10 已经否决，不进入本目录。

1. agent-pr-evidence。现有做法是使用 [vasinl124/max-skills](https://github.com/vasinl124/max-skills) 的 pr-screenshots 与 pr-video，配合 `gh pr` 的附件参数和 Playwright 截图。
2. skill-client-compat。现有做法是使用 [skilldoctor](https://github.com/xyiqq/skilldoctor)。
3. worktree-agent-map。现有做法是使用 [max-sixty/worktrunk](https://github.com/max-sixty/worktrunk) 的 `wt list`。
4. skill-source-drift 不并入本产品，是否单独收录另行决定。

## 仓位

本点子放在 [idea-products](https://github.com/yq6666-66/idea-products) 的 `products/skill-deps-gate/`，不另开仓库。
