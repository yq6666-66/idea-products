# gitignore-audit

进一个 git 仓库目录，一次输出两张清单：已入库却命中忽略规则的文件，和没入库、但长得像构建产物或本地文件的文件，提交前扫一次，防两类错：该忽略的进了仓库，不该忽略的反而没进来。

1. 用法：`python3 gitignore-audit.py <仓库目录> [--json]`，默认打两张表，末尾一行汇总（已入库命中数、未入库疑似数、跳过的项及原因）；加 `--json` 则输出两个数组（`tracked_ignored`、`untracked_suspected`），汇总打到 stderr。
2. 判定分工：清单 A 跑 `git ls-files --cached --ignored --exclude-standard`，每条再用 `git check-ignore -v --no-index` 查规则来源（哪个 `.gitignore` 文件、第几行、哪条规则）；清单 B 跑 `git ls-files --others --exclude-standard`，再按内置产物长相表过滤（`node_modules`、`__pycache__`、`dist`、`build`、`target`、`.venv`、`venv`、`.egg-info`、`.cache` 等目录，`.pyc`、`.pyo`、`.log`、`.tmp`、`.DS_Store`、`.env`、`.swp` 等后缀），命中表的列为“疑似”，不等于判定；否定规则、`exclude` 和全局 gitignore 都以 git 自身的匹配为准，脚本不自己算优先级。
3. 红线：只读，不执行 `git add`、`git rm`、`git clean`，不改 `.gitignore`，不删任何文件，不装任何依赖；只列路径，不打印文件内容；建议方向只写字不执行（清单 A 建议 `git rm --cached`，清单 B 建议加入 `.gitignore` 或删除）。
4. 已知局限：产物长相表是启发式，会误报（比如有的项目就是要把 `dist` 提交），输出里标“疑似”；不判断文件内容是否含密钥，只列路径；依赖 git 命令行已安装，不是 git 仓库时退出码为 2 并明说原因；`.gitignore` 缺失时明说，清单 A 为空，清单 B 仍按产物表跑；大仓库单次扫描可能慢，不做缓存。

演示：[demo.py](./demo.py)，运行 `python3 demo.py`，只在它自己的临时目录里造一个示例 git 仓库，打印两张清单，然后清掉临时目录，不改任何文件。

自测：`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q`
