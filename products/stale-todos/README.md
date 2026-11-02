# stale-todos

扫代码里的 `TODO` / `FIXME`，用 `git blame` 取引入日期，按年龄从老到新列表。只读。

成熟替代：[todoage](https://github.com/jjdoor/todoage)、[todox](https://github.com/phyten/todox)（`todox --with-age --sort -age`）。本 MVP 是零依赖小脚本。

## 跑法

```bash
python3 scan.py /path/to/repo
```

## 试跑建议

先在 408 插件仓库上跑，看最老几条是不是你本来就知道的。

默认只扫注释里的 TODO/FIXME，并跳过测试/夹具路径；需要扫测试时加 `--include-tests`（仍跳过字符串字面量）。

## 自测

```bash
cd products/stale-todos
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```
