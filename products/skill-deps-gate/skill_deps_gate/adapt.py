"""Adapt frontmatter into requirements. Declaration field names stay here."""

from __future__ import annotations

from dataclasses import dataclass

# Keys that this gate does not evaluate. Presence is allowed so ordinary
# skill metadata is not mistaken for a dependency dialect.
IGNORED_TOP = {"license", "compatibility", "metadata", "allowed-tools"}
ALLOWED_TOP = {"name", "description", "dependencies", "requires-mcp-servers"} | IGNORED_TOP


class DeclarationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class Need:
    dependency: str
    kind_label: str
    pool: str
    group: str


@dataclass(frozen=True)
class Adapted:
    skill: str
    needs: tuple[Need, ...]
    bound_server: str | None = None


@dataclass(frozen=True)
class Refusal:
    skill: str
    rows: tuple[tuple[str, str, str, str], ...]
    stderr: str


def adapt(data: dict, directory_name: str) -> Adapted | Refusal:
    skill = _skill_name(data, directory_name)
    _require_optional_string(data, "description")
    unknown = [key for key in data if key not in ALLOWED_TOP]
    if unknown:
        return _unsupported(skill, f"未知字段 {unknown[0]}")
    has_dependencies = "dependencies" in data
    has_servers = "requires-mcp-servers" in data
    if not has_dependencies and not has_servers:
        return Refusal(
            skill,
            ((skill, "(无)", "声明", "空声明"),),
            "unsatisfied: 没有受支持的依赖声明，拒绝视为通过",
        )
    needs: list[Need] = []
    if has_dependencies:
        tool_needs = _tools(data["dependencies"])
        if isinstance(tool_needs, str):
            return _unsupported(skill, tool_needs)
        needs.extend(tool_needs)
    if has_servers:
        for server in _string_list(data["requires-mcp-servers"]):
            needs.append(Need(server, "requires-mcp-servers", "server", "server"))
    if not _has_concrete_requirement(needs):
        return Refusal(
            skill,
            ((skill, "(无)", "声明", "空声明"),),
            "unsatisfied: 依赖声明为空，拒绝视为通过",
        )
    server_names: list[str] = []
    seen_servers: set[str] = set()
    tool_count = 0
    for need in needs:
        if need.pool == "tool":
            tool_count += 1
            continue
        if need.dependency in seen_servers:
            continue
        seen_servers.add(need.dependency)
        server_names.append(need.dependency)
    if tool_count and len(server_names) > 1:
        return Refusal(
            skill,
            ((skill, "requires-mcp-servers", "不支持", "不支持"),),
            "unsupported: 多个服务器与工具声明的绑定尚未支持，拒绝猜成交叉积",
        )
    bound_server = server_names[0] if tool_count and len(server_names) == 1 else None
    return Adapted(skill, tuple(needs), bound_server)


def _has_concrete_requirement(needs: list[Need]) -> bool:
    for need in needs:
        if need.group == "any-empty":
            return True
        if need.dependency:
            return True
    return False


def _tools(node: object) -> list[Need] | str:
    if not isinstance(node, dict):
        raise DeclarationError("依赖声明格式不正确")
    extra_dependency_keys = [key for key in node if key != "tools"]
    if extra_dependency_keys:
        return f"未知字段 dependencies.{extra_dependency_keys[0]}"
    tools = node.get("tools", {})
    if tools is None:
        tools = {}
    if isinstance(tools, list):
        raise DeclarationError("依赖声明格式不正确")
    if not isinstance(tools, dict):
        raise DeclarationError("依赖声明格式不正确")
    extra_tool_keys = [key for key in tools if key not in {"all", "any"}]
    if extra_tool_keys:
        return f"未知字段 dependencies.tools.{extra_tool_keys[0]}"
    needs: list[Need] = []
    if "all" in tools:
        needs.extend(
            Need(item, "tools.all", "tool", "all") for item in _string_list(tools["all"])
        )
    if "any" in tools:
        items = _string_list(tools["any"])
        if items:
            needs.extend(Need(item, "tools.any", "tool", "any") for item in items)
        else:
            needs.append(Need("(空)", "tools.any", "tool", "any-empty"))
    return needs


def _unsupported(skill: str, label: str) -> Refusal:
    stderr = f"unsupported: {label}"
    return Refusal(skill, ((skill, label, "不支持", "不支持"),), stderr)


def _skill_name(data: dict, directory_name: str) -> str:
    if "name" not in data:
        return directory_name
    name = data["name"]
    if not isinstance(name, str) or name == "":
        raise DeclarationError("依赖声明格式不正确")
    return name


def _require_optional_string(data: dict, key: str) -> None:
    if key in data and not isinstance(data[key], str):
        raise DeclarationError("依赖声明格式不正确")


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DeclarationError("依赖声明格式不正确")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            raise DeclarationError("依赖声明格式不正确")
        items.append(item)
    return tuple(items)
