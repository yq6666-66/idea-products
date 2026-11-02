# port-check

输入端口就告诉你是谁占着，顺带列出常用开发端口的状态，不杀进程、不改配置。

1. 用法：`python3 port-check.py 7897 5173 3000`，或 `python3 port-check.py --common` 查 7897、5173、3000、8000、8080；先用 TCP 连接判断监听与否，再用 `ss -tlnp`（Linux）或 `netstat -ano`（Windows）找进程名。
2. 启动命令：能读到 pid 时，Linux 读 `/proc/<pid>/cmdline`，Windows 尽量用 wmic 或 tasklist 补齐；读不到就写“command unknown”，不猜。
3. 只读：找不到进程就写“进程未知”；只查命令行里给出的端口，不动其他配置。
4. 边界：本机结果只对运行它的机器有效。

试跑：2026-11-02 在 Linux VM 上，临时 HTTP 服务起起来后正确报出 LISTENING、属主 python3 和 pid，`--common` 五个端口在 VM 上均为 free。Windows 上的 7897 代理端口和开发服务器端口仍需在 Windows 上单独跑，VM 上 7897 空闲不等于 Windows 上 Surge 的状态。
