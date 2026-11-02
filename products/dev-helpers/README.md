# dev-helpers

三个只读的开发小工具，Python 3 标准库，不删文件、不升级依赖、不杀进程，Linux 和 Windows 都能跑。

1. 日志瘦身报告：`python3 log-slimmer.py <目录> [--top N] [--plan --older-than-days D]`，按大小列出 `*.log`；`--plan` 只打印超过 D 天、会被归档的清单，仍不做任何动作。
2. 依赖速查：`python3 dep-scan.py <项目目录>`，读 `package.json` 和 `requirements.txt`，对照已装版本；`pip audit` 或 `npm audit` 有就跑、没有就明说跳过，绝不编造漏洞数据。
3. 端口占用速查：`python3 port-check.py 7897 5173 3000`，先用 TCP 连接判断监听与否，再用 `ss -tlnp`（Linux）或 `netstat -ano`（Windows）找进程名；找不到就写“进程未知”，不猜。

试跑：2026-11-01 在 Linux VM 上用假数据和真实小数据通过，日志按大小排序、`--plan` 只标超期文件、依赖对照与端口空闲/监听均与预期一致，全程未动任何文件。Windows 上的真实日志目录、真实仓库和 7897 端口仍待在 Windows 上单独跑，VM 结果不能冒充 Windows 结果。

后续版本仍需先备份、再经确认才做归档，升级也只出清单、不自动升级；这两项不在本次 MVP 里。
