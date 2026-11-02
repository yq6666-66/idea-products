# stale-todos

扫代码里的 `TODO` / `FIXME`，用 `git blame` 取引入日期，按年龄从老到新列表。只读。

成熟替代：[todoage](https://github.com/jjdoor/todoage)、[todox](https://github.com/phyten/todox)（`todox --with-age --sort -age`）。本 MVP 是零依赖小脚本。

## 跑法

```bash
python3 scan.py /path/to/repo
```

## 演示

演示入口：<https://github.com/yq6666-66/idea-products/blob/main/products/stale-todos/demo/run.py>

`demo/run.py` 在临时目录建一个小仓库，写入三条不同日期的注释（2024-01-15 的 TODO、2025-06-01 的 FIXME、2026-11-01 的 TODO），外加一行字符串里的 TODO。不访问网络。需要本机有 `git`。在本目录执行：

```bash
python3 demo/run.py
```

字符串那行不会出现。`count: 3`。天数按运行当天算，日期和路径不变。2026-11-02 跑出来是：

```
count: 3
2024-01-15  1022d  TODO   src/parser.py:1  # TODO: replace the hand-rolled splitter
2025-06-01   519d  FIXME  src/io.py:2  # FIXME: empty files should return None
```

同一次输出里还有 `2026-11-01     1d  TODO   src/app.py:1`。同文件的 `msg = "TODO: ..."` 被跳过。

默认只扫注释里的 TODO/FIXME，并跳过测试/夹具路径；需要扫测试时加 `--include-tests`（仍跳过字符串字面量）。

## 自测

```bash
cd products/stale-todos
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```
