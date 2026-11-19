"""Locate SKILL.md files. Symlinks are refused instead of followed."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FoundSkill:
    display: str
    directory_name: str
    skill_md: Path


def supplied_path_has_symlink(raw: str) -> bool:
    """True when any lexical component of a supplied path is a symlink.

    The check does not resolve the path first, so an ancestor symlink is visible.
    It does not inspect how the process entered its current directory.
    """
    path = Path(raw)
    if path.is_absolute():
        current = Path(path.anchor)
        parts = path.parts[1:]
    else:
        current = Path()
        parts = path.parts
    for part in parts:
        if part == ".":
            continue
        current = Path(part) if current == Path() else current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return False
    return False


def discover(raw_roots: list[str]) -> tuple[list[FoundSkill], list[str]]:
    found: list[FoundSkill] = []
    errors: list[str] = []
    for raw in raw_roots:
        if supplied_path_has_symlink(raw):
            errors.append(f"{raw}: 符号链接不允许")
            continue
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
            if skill_md.exists():
                if not _is_regular_file(skill_md):
                    errors.append(f"{raw}: SKILL.md不是普通文件")
                    continue
                found.append(FoundSkill(_display(raw), path.name, skill_md))
                continue
        except OSError:
            errors.append(f"{raw}: 目录不可读")
            continue
        nested, nested_errors = _walk(path, raw)
        errors.extend(nested_errors)
        found.extend(nested)
        if not nested and not nested_errors:
            errors.append(f"{raw}: 没有找到 SKILL.md")
    return found, errors


def _walk(root: Path, display_root: str) -> tuple[list[FoundSkill], list[str]]:
    found: list[FoundSkill] = []
    errors: list[str] = []
    try:
        boundary = root.resolve()
    except OSError:
        return [], [f"{display_root}: 目录不可读"]
    def _onerror(err: OSError) -> None:
        name = getattr(err, "filename", None) or display_root
        errors.append(f"{name}: 目录不可读")

    try:
        walker = os.walk(root, followlinks=False, onerror=_onerror)
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
            if not _is_regular_file(skill_md):
                errors.append(f"{_display(display_root, skill_md, root)}: SKILL.md不是普通文件")
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


def _is_regular_file(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode)


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
