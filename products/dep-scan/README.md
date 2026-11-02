# dep-scan

一次扫完一个项目的依赖，列出已装与未装对照和审计提示，不自动升级。

1. 用法：`python3 dep-scan.py <项目目录>`，读 `package.json` 和 `requirements.txt`，Node 对照 `node_modules`，Python 对照当前环境。
2. 只读：不升级、不安装、不卸载、不改任何文件；`pip audit` 或 `npm audit` 有就跑、没有就明说跳过，绝不编造漏洞数据。
3. 注意：这和 10 月 30 日健康看板里的依赖项有重叠，本产品是把那一项单独抽出来的窄版，只做依赖速查，不做看板的其他健康项。

试跑：对去黑点仓库的本地副本实测，该仓库无 `package.json`、无 `requirements.txt`，脚本如实报“无”且未下过期结论，这是正确的空结果，不是漏报；对一个真实的 requirements.txt 实测，requests 报已装 2.31.0、numpy 报 1.26.4、Pillow 报 10.2.0，未装的包如实报未安装。按严重程度排序的漏洞表不在本次 MVP 里，审计只给出工具有无和退出情况。
