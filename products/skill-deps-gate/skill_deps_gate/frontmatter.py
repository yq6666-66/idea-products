"""Extract YAML frontmatter with SafeLoader. The skill body is never executed."""

from __future__ import annotations

import yaml
from yaml.constructor import ConstructorError


class FrontmatterError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys."""


def _construct_mapping(loader: StrictLoader, node: yaml.Node, deep: bool = False) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _is_delimiter(line: str) -> bool:
    text = line[:-1] if line.endswith("\n") else line
    if text.endswith("\r"):
        text = text[:-1]
    return text == "---"


def read_frontmatter(text: str) -> dict:
    lines = text.splitlines(keepends=True)
    if not lines or not _is_delimiter(lines[0]):
        raise FrontmatterError("frontmatter 解析失败")
    closing = None
    for index in range(1, len(lines)):
        if _is_delimiter(lines[index]):
            closing = index
            break
    if closing is None:
        raise FrontmatterError("frontmatter 解析失败")
    block = "".join(lines[1:closing])
    try:
        loaded = yaml.load(block, Loader=StrictLoader)  # noqa: S506  SafeLoader subclass
    except yaml.YAMLError as exc:
        detail = " ".join(str(exc).split())
        raise FrontmatterError(f"frontmatter 解析失败: {detail}") from exc
    if not isinstance(loaded, dict):
        raise FrontmatterError("frontmatter 不是映射")
    return loaded
