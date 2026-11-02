# dep-scan

一次扫完一个项目的依赖，列出过期项和已知漏洞，按严重程度排序，不自动升级。

1. 用法：`python3 dep-scan.py <项目目录> [--check-latest]`，读 `package.json` 和 `requirements.txt`，Node 对照 `node_modules`，Python 对照当前环境。
2. 过期对照：`--check-latest` 时从 PyPI 或 npm registry 取最新版，标 OUTDATED、UP-TO-DATE 或 UNKNOWN；取不到就写 UNKNOWN，不编版本号。
3. 漏洞：解析 `pip audit` 或 `npm audit` 的 JSON，按 critical、high、moderate、low、info 排序输出，pip audit 本身没有严重程度字段的排在最后并标 unknown；审计工具没有就明说跳过，绝不编造漏洞数据。
4. 只读：不升级、不安装、不卸载、不改任何文件，输出只是升级清单。
5. 注意：这和 10 月 30 日健康看板里的依赖项有重叠，本产品是把那一项单独抽出来的窄版，只做依赖速查，不做看板的其他健康项。

试跑：对去黑点仓库的本地副本实测，该仓库无 `package.json`、无 `requirements.txt`，脚本如实报“无”且未下过期结论，这是正确的空结果；对一个真实的 requirements.txt 实测，requests 已装 2.31.0、最新 2.34.2，标 OUTDATED，numpy 已装 1.26.4、最新 2.5.4，标 OUTDATED，不存在的包标 UNKNOWN；pip audit 在该环境不可用，明说跳过。
