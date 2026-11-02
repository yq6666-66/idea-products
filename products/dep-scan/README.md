# dep-scan

一次扫完一个项目的依赖，列出过期项和已知漏洞，按严重程度排序，不自动升级。

1. 用法：`python3 dep-scan.py <项目目录> [--check-latest]`，读 `package.json` 和 `requirements.txt`，Node 对照 `node_modules`，Python 对照当前环境。
2. 过期对照：`--check-latest` 时从 PyPI 或 npm registry 取最新版，标 OUTDATED、UP-TO-DATE 或 UNKNOWN；取不到就写 UNKNOWN，不编版本号。
3. 漏洞：解析 `pip audit` 或 `npm audit` 的 JSON，按 critical、high、moderate、low、info 排序输出，pip audit 本身没有严重程度字段的排在最后并标 unknown；审计工具没有就明说跳过，绝不编造漏洞数据。
4. 只读：不升级、不安装、不卸载、不改任何文件，输出只是升级清单。

夹具：不读取任何外部仓库。演示只使用脚本自己在临时目录里写下的示例依赖清单。

演示：`python3 demo.py`，只在它自己的临时目录里造一个示例项目，打印依赖报告，然后清掉临时目录，不升级任何东西。

自测：`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q`
