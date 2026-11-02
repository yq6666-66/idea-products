# idea-products

点子产品库。把日常冒出来的点子做成可开源的小工具，一个点子对应 `products/` 下的一个子目录，每个产品各自独立。

## 约定

每个产品尽量保持单脚本或极小 CLI，默认只读，不自动删改仓库内容。上传新产品前，先核对是否已有成熟开源项目完全覆盖；有就直接用，不必重复造轮子。

## 目录

见 [`products/`](./products/)，每个子目录是一个独立产品：

1. [`log-slimmer`](./products/log-slimmer/)：日志按大小列出，超期清单先 dry-run，备份后才归档，原文件不删。演示：[demo.py](./products/log-slimmer/demo.py)。
2. [`dep-scan`](./products/dep-scan/)：扫一个项目的依赖，对照已装与最新版，漏洞按严重程度排序，只出升级清单，不自动升级。演示：[demo.py](./products/dep-scan/demo.py)。
3. [`port-check`](./products/port-check/)：输入端口报出属主进程和启动命令，`--common` 查常用开发端口，不杀进程。演示：[demo.py](./products/port-check/demo.py)。
4. [`md-dead-links`](./products/md-dead-links/)：扫仓库 Markdown 的本地与外链，报告断链和超时，不改文件。
   演示：<https://github.com/yq6666-66/idea-products/tree/main/products/md-dead-links/demo>（在产品目录执行 `python3 check.py demo`）
5. [`worktree-cleanup-preview`](./products/worktree-cleanup-preview/)：只读预览可能没用的 worktree 和已合进主线的本地分支，不删除任何东西。
   演示：<https://github.com/yq6666-66/idea-products/blob/main/products/worktree-cleanup-preview/demo/run.py>（在产品目录执行 `python3 demo/run.py`）
6. [`stale-todos`](./products/stale-todos/)：扫代码注释里的 TODO 与 FIXME，用 git blame 按年龄排序，只读。
   演示：<https://github.com/yq6666-66/idea-products/blob/main/products/stale-todos/demo/run.py>（在产品目录执行 `python3 demo/run.py`）

## 许可

MIT。详见 [LICENSE](./LICENSE)。
