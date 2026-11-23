"""YAML frontmatter 的最小解析，避免引入 PyYAML 依赖。

只支持本项目实际用到的写法：
  key: value
  key:
    - item
"""
from __future__ import annotations

import re
from pathlib import Path


def parse(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text

    data: dict = {}
    key: str | None = None
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if key is not None:
                if not isinstance(data.get(key), list):
                    data[key] = []
                data[key].append(stripped[2:].strip())
            continue
        m = re.match(r"^([^:：]+)[：:]\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).strip()
        value = m.group(2).strip()
        data[key] = [] if value == "" else value
    body = "\n".join(lines[end + 1:])
    return data, body


def read(path: Path) -> tuple[dict, str]:
    return parse(path.read_text(encoding="utf-8"))


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v]
    return [str(value)]


def set_field(text: str, key: str, value: str) -> str:
    """在 frontmatter 内替换 key 对应的一行。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return text
    pattern = re.compile(r"^([^:：]+)[：:]\s*")
    for i in range(1, end):
        m = pattern.match(lines[i])
        if m and m.group(1).strip() == key:
            lines[i] = f"{key}: {value}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    # 没找到就插在结尾分隔线之前
    lines.insert(end, f"{key}: {value}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
