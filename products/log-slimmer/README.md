# log-slimmer

只对你自己的日志目录做瘦身，先报出哪些文件最大，再决定压缩还是归档。

1. 用法：`python3 log-slimmer.py <目录> [--top N] [--plan --older-than-days D]`，按大小列出 `*.log`。
2. 默认只读：不删、不压缩；`--plan` 只打印超过 D 天、会被归档的清单。
3. 归档是显式三件套才动：`--archive --backup-dir <备份目录> --archive-dir <归档目录> --confirm-archive`，先把原文件原样复制到备份目录，再把内容写成 `.gz` 放到归档目录，原文件始终不动、不删；备份和归档目录必须在被扫目录之外，否则直接拒绝。
4. 边界：只扫你自己的目录，不指向备份或未知来源文件。

试跑：2026-11-02 在 Linux VM 上用假数据通过，无确认时归档被拒绝且什么都没动；有确认时备份哈希与原文件一致、`.gz` 解压后与原文件一致、原文件仍在且哈希不变。机器人、NapCat、Railway 这类真实日志目录仍需在产生日志的机器上单独跑，VM 结果不能冒充。

演示：`python3 demo.py`，只在它自己的临时目录里造三个假日志，打印报告和 --plan，然后清掉临时目录。

自测：`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q`
