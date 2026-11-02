# products

每个子目录是一个独立小产品，互不混用。建议结构：

```
products/<name>/
  README.md   # 一句话用途、怎么跑、试跑仓库
  <script>    # 主入口
```

当前产品：

1. `log-slimmer/`：日志按大小列出，超期清单先 dry-run，备份后才归档。
2. `dep-scan/`：依赖已装与最新版对照，漏洞按严重程度排序，只出升级清单。
3. `port-check/`：端口属主进程与启动命令速查，不杀进程。
4. `md-dead-links/`：Markdown 断链与超时报告。
5. `worktree-cleanup-preview/`：worktree 与已合并分支的只读预览。
6. `stale-todos/`：TODO 与 FIXME 按引入年龄排序的只读扫描。
