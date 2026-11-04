# startup-cmds

进一个项目目录，一次列出它所有能跑的启动命令，不用翻 `package.json`、Makefile、justfile、`pyproject.toml` 四个文件。

1. 用法：`python3 startup-cmds.py <项目目录> [--json]`，默认打表（命令名、来源文件、来源小节、实际命令体），末尾一行汇总（扫了几个文件、出了几条命令、跳过了几个文件及原因）；加 `--json` 则输出命令对象数组，汇总打到 stderr。
2. 解析分工：`package.json` 读 `scripts`；Makefile 只认行首目标名加冒号的形式，排除 `.PHONY` 等特殊目标和含 `%` 的模式规则，目标后的注释一并带上；justfile 认行首 recipe 名加冒号的形式，排除以下划线开头的私有 recipe，带参数的 recipe 在命令名后标注参数占位；`pyproject.toml` 读 `[project.scripts]` 和 `[tool.poetry.scripts]` 两个表。
3. 红线：只读，不执行任何命令，不改任何文件，不装任何依赖；读不到、读不懂的文件明说跳过，不编造命令；同名命令出现在多个文件时逐行列出，不合并去重。
4. 已知局限：Makefile 的变量展开和 include 不做解析，命令体里带 `$(...)` 的按原文展示；justfile 的参数默认值不展开，只标注占位；`pyproject.toml` 需要 Python 3.11 以上的 `tomllib`，低版本报不支持而不是悄悄跳过；目录不存在时退出码为 2。

演示：[demo.py](./demo.py)，运行 `python3 demo.py`，只在它自己的临时目录里造一个示例项目，打印启动命令表，然后清掉临时目录，不执行任何命令。

自测：`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q`
