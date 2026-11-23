"""把会话日志汇总成 CSV，供复盘与统计。

用法：
    python tools/export_stats.py sessions --out stats.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm  # noqa: E402

COLUMNS = [
    "session_id", "剧本id", "规则系统", "场次", "时长分钟", "主线节点", "结果",
    "检定数", "明投数", "暗投数", "失败数", "失败率", "审核退回卡数",
]


def count_checks(body: str) -> tuple[int, int, int, int]:
    """返回 (检定数, 明投数, 暗投数, 失败数)。"""
    in_section = False
    total = open_ = hidden = failed = 0
    header_seen = False
    for line in body.splitlines():
        if line.startswith("## "):
            in_section = "检定记录" in line
            header_seen = False
            continue
        if not in_section or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if not header_seen:
            header_seen = True
            continue
        if set(cells[0]) <= {"-", " ", ":"}:
            continue
        if not cells[0]:
            continue
        total += 1
        if "暗投" in cells[2]:
            hidden += 1
        else:
            open_ += 1
        if "失败" in cells[4]:
            failed += 1
    return total, open_, hidden, failed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions_dir", nargs="?", default="sessions")
    ap.add_argument("--out", default="stats.csv")
    args = ap.parse_args()

    root = Path(args.sessions_dir)
    if not root.is_dir():
        print(f"找不到目录：{root}")
        return 2

    rows = []
    # 递归收集会话：sessions/<id> 与 sessions/local/<id> 都要认
    candidates = sorted(
        p for p in root.rglob("*")
        if p.is_dir() and (p / "00-本次设定.md").exists()
    )
    for session in candidates:
        if session.name == "_template":
            continue
        man_path = session / "00-本次设定.md"
        if not man_path.exists():
            continue
        man, _ = fm.read(man_path)

        rejected = 0
        for card in (session / "01-车卡").glob("*.md"):
            if card.name.startswith("_"):
                continue
            _, body = fm.read(card)
            if "退回" in body:
                rejected += 1

        logs = sorted((session / "03-日志").glob("日志-*.md")) if (session / "03-日志").exists() else []
        if not logs:
            rows.append({
                **{k: "" for k in COLUMNS},
                "session_id": session.name,
                "剧本id": man.get("剧本id", ""),
                "规则系统": man.get("规则系统", ""),
                "审核退回卡数": rejected,
            })
            continue

        for log in logs:
            lfm, body = fm.read(log)
            total, open_, hidden, failed = count_checks(body)
            rows.append({
                "session_id": session.name,
                "剧本id": man.get("剧本id", ""),
                "规则系统": man.get("规则系统", ""),
                "场次": lfm.get("场次", ""),
                "时长分钟": lfm.get("时长分钟", ""),
                "主线节点": lfm.get("主线节点", ""),
                "结果": lfm.get("结果", ""),
                "检定数": total,
                "明投数": open_,
                "暗投数": hidden,
                "失败数": failed,
                "失败率": round(failed / total, 2) if total else "",
                "审核退回卡数": rejected,
            })

    out = Path(args.out)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"已导出 {len(rows)} 行 → {out.resolve()}")
    if rows:
        total_checks = sum(r["检定数"] or 0 for r in rows)
        total_fail = sum(r["失败数"] or 0 for r in rows)
        total_hidden = sum(r["暗投数"] or 0 for r in rows)
        print(f"检定 {total_checks} 次，失败 {total_fail} 次"
              + (f"（失败率 {total_fail/total_checks:.0%}）" if total_checks else "")
              + f"，其中暗投 {total_hidden} 次")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
