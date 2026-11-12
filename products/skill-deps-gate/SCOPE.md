# skill-deps-gate 范围

实现状态：PLANNED / NOT IMPLEMENTED。

日期：2026-11-12（北京时间）。本文只收录范围。实现尚未开始，本文不是样本开发授权。本次没有代码、夹具、持续集成配置，也没有 PATH 探测实现。点子见 [IDEA.md](./IDEA.md)。

## 目标

做一个只读命令行工具。在加载 Skill 之前，对照当前环境的 MCP `tools/list` 检查 `SKILL.md` 声明的工具依赖。PATH 命令探测是后续可选项。缺什么就立刻以非零状态退出，避免 agent 跑到一半才报错，或幻觉出当前环境没有的能力。

后续 MVP 保持本地只读，不依赖付费服务。本次收录不产生实现，也不代表版本发布。

## 后续 MVP 必须守住

下列条目属于后续实现范围。本次不实现。

1. 只读扫描本地 skill 目录，解析 frontmatter 里的依赖声明。
2. 解析层同时保留三种声明：`dependencies.tools.all`、`dependencies.tools.any`，以及常见的 `requires-mcp-servers`。形状对齐 [agentskills issue 485](https://github.com/agentskills/agentskills/issues/485)。草案字段若变化，只改解析适配层，不把实现绑死在单一字段名上。2026-11-10 调研时该议题仍为 open。本文不宣称 2026-11-12 复核了该状态。
3. 运行时输入一份本机 MCP `tools/list` 快照 JSON。
4. PATH 探测留在后续可选能力里，不进入样本 1。
5. 输出「Skill × 依赖」满足矩阵。任一必选依赖不满足则非零退出，供日后持续集成使用。本次不接入本仓库的持续集成。
6. 不做安装，不做编排，不做安全扫描。

不得混入本目录的方向：

1. agent-pr-evidence。
2. skill-client-compat。
3. worktree-agent-map。
4. skill-source-drift。

mcp-tool-drift 与 agent-perm-matrix 是相邻轴。本产品只回答声明的依赖是否被当前工具表满足。

## 样本 1

样本 1 尚未开始。它不在本次收录里实现。确认之后只做这一步，做完即停。

样本 1 只包含这些内容：`dependencies.tools.all` 声明、`requires-mcp-servers` 声明、一份依赖全部满足的快照、一份缺少依赖的快照，以及对应退出码。`dependencies.tools.any` 留在后续 MVP，不写入样本 1 的声明。PATH 探测不进入样本 1。

完成标准如下。

1. 从哪里进入：在本机命令行调用该工具，传入虚构 skill 目录路径和 `tools/list` 快照路径。
2. 需要输入什么：一份带 frontmatter 的虚构 `SKILL.md`。其中至少声明 `dependencies.tools.all` 的一个工具名，并带上可被适配层识别的 `requires-mcp-servers`。另有两份快照，一份包含全部所需工具，一份缺少其中之一。
3. 成功后看到什么：使用满足快照时，标准输出给出该 Skill 与各依赖的满足矩阵，每条必选依赖标记为满足，进程退出码为 0。
4. 数据发生什么变化：只读。不修改被扫描目录，不安装 MCP，不改 PATH，不写入用户配置。
5. 失败时如何展示：使用缺失快照时，仍输出矩阵并标明缺了哪一项，进程退出码非 0。快照文件缺失、目录不存在或 frontmatter 无法解析时，也要非零退出并写明原因，不得假装检查通过。

样本 1 同时不做下面这些事。

1. 不扫描真实用户目录。
2. 不做 PATH 探测。
3. 不接入本仓库持续集成。
4. 不编写对外 README。

## 样本 1 之后才单独决定的事

1. 样本 2 等样本 1 通过后再定范围。预留方向是真实的多 skill 目录扫描，或可选的 PATH 探测。这两项不得在同一步做完。
2. 把可运行实现放进本目录，以及为本产品添加最小持续集成，都要单独决定。本次不做。
3. 产品 README 和仓库目录索引由后续单独补充。本次不修改任何 README。

## 本次边界

1. 只新增本目录的点子文档、范围文档和 changelog。
2. 状态保持 PLANNED / NOT IMPLEMENTED。
3. 没有代码，没有夹具，没有持续集成配置，没有 PATH 探测实现。
4. 没有版本发布。
