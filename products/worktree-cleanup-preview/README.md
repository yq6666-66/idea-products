# worktree-cleanup-preview

只读预览：列出可能没用的 orphan/stale worktree，以及已合进主线的本地分支。默认不删除任何东西。

## 跑法

```bash
python3 preview.py /path/to/repo
```

可选：`--base main`（默认自动猜 `main`/`master`）。

## 试跑建议

先在多分支仓库（例如 no-markdown-bullets）上跑一遍，核对「已合并分支」是否准确。
