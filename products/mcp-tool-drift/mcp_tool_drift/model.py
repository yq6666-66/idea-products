from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServerSpec:
    client: str
    name: str
    command: str | None
    args: tuple[str, ...]
    url: str | None
    env: dict[str, str]


def parse_servers(data: dict, client: str) -> list[ServerSpec]:
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be an object")
    parsed: list[ServerSpec] = []
    for name, spec in servers.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ValueError(f"invalid server entry: {name!r}")
        command = spec.get("command")
        url = spec.get("url")
        args = spec.get("args") or []
        env = spec.get("env") or {}
        if command is not None and not isinstance(command, str):
            raise ValueError(f"command must be a string for {name}")
        if url is not None and not isinstance(url, str):
            raise ValueError(f"url must be a string for {name}")
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError(f"args must be a list of strings for {name}")
        if not isinstance(env, dict):
            raise ValueError(f"env must be an object for {name}")
        parsed.append(
            ServerSpec(
                client=client,
                name=name,
                command=command or None,
                args=tuple(args),
                url=url or None,
                env={str(key): str(value) for key, value in env.items()},
            )
        )
    return parsed


def format_server(server: ServerSpec) -> str:
    """One log line. Env values are always masked."""
    args = " ".join(server.args)
    masked = ",".join(f"{key}=***" for key in sorted(server.env))
    return (
        f"{server.client}\t{server.name}\t"
        f"command={server.command or '-'}\t"
        f"args={args}\t"
        f"url={server.url or '-'}\t"
        f"env={masked}"
    )


def redact(text: str, env: dict[str, str]) -> str:
    for value in env.values():
        if value:
            text = text.replace(value, "***")
    return text
