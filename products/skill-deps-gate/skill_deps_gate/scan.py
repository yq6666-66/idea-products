"""Locate SKILL.md files. Symlinks are refused instead of followed."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FoundSkill:
    display: str
    directory_name: str
    skill_md: Path


def discover(raw_roots: list[str]) -> tuple[list[FoundSkill], list[str]]:
    found: list[FoundSkill] = []
    errors: list[str] = []
    for raw in raw_roots:
        path = Path(raw)
        try:
            exists = path.exists()
            is_dir = path.is_dir()
        except OSError:
            errors.append(f"{raw}: 目录不可读")
            continue
        if not exists:
            errors.append(f"{raw}: 找不到 skill 目录")
            continue
        if not is_dir:
            errors.append(f"{raw}: skill 路径不是目录")
            continue
        try:
            readable = os.access(path, os.R_OK | os.X_OK)
        except OSError:
            errors.append(f"{raw}: 目录不可读")
            continue
        if not readable:
            errors.append(f"{raw}: 目录不可读")
            continue
        skill_md = path / "SKILL.md"
        try:
            if skill_md.is_symlink():
                errors.append(f"{raw}: 符号链接不允许")
                continue
            if skill_md.is_file():
                found.append(FoundSkill(_display(raw), path.name, skill_md))
                continue
        except OSError:
            errors.append(f"{raw}: 目录不可读")
            continue
        nested, nested_errors = _walk(path, raw)
        errors.extend(nested_errors)
        if nested_errors:
            continue
        if not nested:
            errors.append(f"{raw}: 没有找到 SKILL.md")
            continue
        found.extend(nested)
    return found, errors


def _walk(root: Path, display_root: str) -> tuple[list[FoundSkill], list[str]]:
    found: list[FoundSkill] = []
    errors: list[str] = []
    try:
        boundary = root.resolve()
    except OSError:
        return [], [f"{display_root}: 目录不可读"]
    try:
        walker = os.walk(root, followlinks=False)
    except OSError:
        return [], [f"{display_root}: 目录不可读"]
    try:
        for current, dirnames, filenames in walker:
            current_path = Path(current)
            kept: list[str] = []
            for name in dirnames:
                child = current_path / name
                if child.is_symlink() or _escapes(child, boundary):
                    errors.append(f"{_display(display_root, child, root)}: 符号链接不允许")
                    continue
                kept.append(name)
            dirnames[:] = kept
            if "SKILL.md" not in filenames:
                continue
            skill_md = current_path / "SKILL.md"
            if skill_md.is_symlink() or _escapes(skill_md, boundary):
                errors.append(f"{_display(display_root, skill_md, root)}: 符号链接不允许")
                continue
            found.append(
                FoundSkill(
                    _display(display_root, current_path, root),
                    current_path.name,
                    skill_md,
                )
            )
    except OSError:
        errors.append(f"{display_root}: 目录不可读")
    found.sort(key=lambda item: item.display)
    return found, errors


def _escapes(path: Path, boundary: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        resolved = path.resolve()
    except OSError:
        return True
    try:
        resolved.relative_to(boundary)
    except ValueError:
        return True
    return True


def _display(root: str, path: Path | None = None, root_path: Path | None = None) -> str:
    text = Path(root).as_posix()
    if path is None or root_path is None:
        return text
    relative = path.relative_to(root_path).as_posix()
    if relative == ".":
        return text
    return f"{text}/{relative}"
