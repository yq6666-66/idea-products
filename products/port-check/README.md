# port-check

输入端口就告诉你是谁占着，顺带列出常用开发端口的状态，不杀进程、不改配置。

1. 用法：`python3 port-check.py 7897 5173 3000`，或 `python3 port-check.py --common` 查 7897、5173、3000、8000、8080；先用 TCP 连接判断监听与否，再用 `ss -tlnp`（Linux）或 `netstat -ano`（Windows）找进程名。
2. 启动命令：能读到 pid 时，Linux 读 `/proc/<pid>/cmdline`，Windows 尽量用 wmic 或 tasklist 补齐；读不到就写“command unknown”，不猜。
3. 只读：找不到进程就写“进程未知”；只查命令行里给出的端口，不动其他配置。
4. 边界：本机结果只对运行它的机器有效。

试跑：临时 HTTP 服务起起来后正确报出 LISTENING、属主 python3 和 pid，`--common` 五个端口在测试环境上均为 free。本机以外的端口状态仍需在那台机器上单独跑。

演示：[demo.py](./demo.py)，运行 `python3 demo.py`，只启动它自己的临时 HTTP 服务，打印该端口和 --common 的结果，然后停掉自己的服务，不碰其他进程。
视频：[演示视频](./videos/demo.mp4)、[技术视频](./videos/technical.mp4)（AI 生成的讲解视频，非真实录屏）。

自测：`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q`
