# md-dead-links

扫仓库里的 Markdown：本地链接查文件是否存在，外链做 HEAD（失败再 GET），超时单独标出。只输出断链表，不改文件。

成熟替代：若你已装 [lychee](https://github.com/lycheeverse/lychee)，可直接 `lychee .`，覆盖面更大。本 MVP 是零依赖小脚本。

## 跑法

```bash
python3 check.py /path/to/repo
```

## 试跑建议

先拿文档多的仓库（例如 no-markdown-bullets）跑一遍，抽查报出的断链是否属实。
