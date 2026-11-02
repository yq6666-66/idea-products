# worktree-cleanup-preview

只读预览：列出可能没用的 orphan/stale worktree，以及已合进主线的本地分支。默认不删除任何东西。

## 跑法

```bash
python3 preview.py /path/to/repo
```

可选：`--base main`（默认自动猜 `main`/`master`）。

## 演示

`demo/run.py` 在临时目录建一个本地仓库：分支 `feature` 已合并进 `main`，另有一个仍在的 worktree，以及一个目录已删掉的游离 worktree。不访问网络，跑完就删。需要本机有 `git`。在本目录执行：

```bash
python3 demo/run.py
```

路径和提交时间每次不同。稳定能看到的是：

```
  flags=branch-merged-into-base
  flags=detached,prunable/orphan
- feature last_commit=<commit-time>
```

## 自测

```bash
cd products/worktree-cleanup-preview
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

