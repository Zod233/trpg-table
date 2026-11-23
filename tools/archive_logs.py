"""归档旧日志：只移动，不删除。

用法：
    python tools/archive_logs.py sessions/2026-11-23-rain-train-01
    python tools/archive_logs.py sessions/... --keep 3
    python tools/archive_logs.py sessions/... --dry-run

规则：03-日志/ 里只留最近 --keep 份「日志-NNN.md」，更早的移到 03-日志/归档/。
归档前要确认这些场次已经进过 `前情提要.md` 的 L2 摘要块，否则会丢内容——脚本会先提示。
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

LOG = re.compile(r"日志-(\d{3})\.md$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--keep", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    session = Path(args.session).resolve()
    logdir = session / "03-日志"
    if not logdir.is_dir():
        print(f"找不到 03-日志/：{session}")
        return 2
    logs = sorted(p for p in logdir.iterdir() if p.is_file() and LOG.search(p.name))
    if len(logs) <= args.keep:
        print(f"共 {len(logs)} 份日志，不超过保留数 {args.keep}，无需归档。")
        return 0

    older = logs[: len(logs) - args.keep]
    recap = logdir / "前情提要.md"
    recap_text = recap.read_text(encoding="utf-8") if recap.exists() else ""
    archivedir = logdir / "归档"
    unsummarised = [
        p.name for p in older
        if f"场次 {LOG.search(p.name).group(1)}" not in recap_text
        and f"块 {LOG.search(p.name).group(1)}" not in recap_text
    ]
    if unsummarised:
        print(f"[提醒] 这些日志未在前情提要.md 找到对应场次/块标记：{', '.join(unsummarised)}")
        print("        先补 L2 摘要块再归档，否则内容只剩归档文件可查。")

    if args.dry_run:
        print(f"[预演] 将归档 {len(older)} 份：{', '.join(p.name for p in older)}")
        return 0

    archivedir.mkdir(exist_ok=True)
    moved = 0
    for p in older:
        target = archivedir / p.name
        if target.exists():
            print(f"[跳过] 归档里已有同名文件：{target.name}")
            continue
        shutil.move(str(p), str(target))
        moved += 1
    print(f"已归档 {moved} 份到 03-日志/归档/，保留 {args.keep} 份在 03-日志/。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
