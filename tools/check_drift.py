"""机械漂移检查：把「跑着跑着就不对了」的几件事用脚本查出来。

用法：
    python tools/check_drift.py sessions/2026-11-23-rain-train-01

查七件事：
1. 日志编号是否连续、frontmatter 场次是否与文件名一致
2. 是否连续两场没有主线推进
3. 承诺是否超期未兑现
4. 观察区是否到期还没处理
5. 未闭指针是否标了「不成立」还挂着
6. 状态跟踪 / L1 是否超装载预算
7. 丢弃清单是否缺留痕

退出码 0 = 没有硬问题（提醒不算），1 = 有漂移，先对账再开局。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm  # noqa: E402

LOG = re.compile(r"日志-(\d{3})\.md$")
NUM = re.compile(r"\d{3}")

drift: list[str] = []
warn: list[str] = []
okn = 0


def ok(msg: str) -> None:
    global okn
    okn += 1
    print(f"[通过] {msg}")


def bad(msg: str) -> None:
    drift.append(msg)
    print(f"[漂移] {msg}")


def soft(msg: str) -> None:
    warn.append(msg)
    print(f"[提醒] {msg}")


def tables(path: Path) -> dict[str, list[list[str]]]:
    """按标题收集 Markdown 表格：{标题: [[数据单元格...]]}（表头与分隔行已剔除）。"""
    out: dict[str, list[list[str]]] = {}
    if not path.exists():
        return out
    head = ""
    rows: list[list[str]] | None = None

    def flush() -> None:
        nonlocal rows
        if rows is not None and head:
            out.setdefault(head, []).extend(rows[1:])
        rows = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            flush()
            head = line.lstrip("#").strip()
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") and c for c in cells):
                continue
            if rows is None:
                rows = [cells]
            else:
                rows.append(cells)
        else:
            flush()
    flush()
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python tools/check_drift.py <会话文件夹>")
        return 2
    session = Path(sys.argv[1]).resolve()
    if not session.is_dir():
        print(f"找不到会话：{session}")
        return 2
    man, _ = fm.read(session / "00-本次设定.md")
    cur = int(str(man.get("当前场次") or "0").strip() or 0)
    total_players = int(str(man.get("玩家数") or "1").strip() or 1)

    logdir = session / "03-日志"
    logs = sorted(p for p in logdir.iterdir() if p.is_file() and LOG.search(p.name)) if logdir.exists() else []
    if not logs:
        bad("03-日志/ 里没有任何 日志-NNN.md")
        return report()

    nums = [int(LOG.search(p.name).group(1)) for p in logs]
    if nums != list(range(1, len(nums) + 1)):
        bad(f"日志编号不连续：{nums}")
    else:
        ok(f"日志编号连续，共 {len(logs)} 场")

    main_progress: list[int] = []
    for p in logs:
        lfm, _ = fm.read(p)
        n = int(LOG.search(p.name).group(1))
        if str(lfm.get("场次") or "").zfill(3) != f"{n:03d}":
            bad(f"{p.name} 的 frontmatter 场次 {lfm.get('场次')} 与文件名不一致")
        if not str(lfm.get("骰源") or ""):
            soft(f"{p.name} 没写骰源，日后无法判断该场骰值能否复核")
        tb = tables(p)
        rows = [r for r in tb.get("事件分级", []) if len(r) >= 3]
        pushed = any(r[1].startswith("主线") and "推进" in r[2] for r in rows)
        main_progress.append(n if pushed else 0)
        dropped = "丢弃清单" in p.read_text(encoding="utf-8")
        if not dropped:
            soft(f"{p.name} 没有「丢弃清单」段，归档时被判为一次性的东西没处留痕")

    run = 0
    for n in main_progress:
        run = 0 if n else run + 1
        if run >= 2:
            bad(f"从场次 {n - 1:03d} 到 {n:03d} 连续两场没有主线推进，主线停滞")
            break
    if not any(x for x in main_progress):
        soft("所有日志都没有标记主线推进，若主线其实在走，说明日志没按模板记")

    st_path = session / "状态跟踪.md"
    st_lines = len(st_path.read_text(encoding="utf-8").splitlines()) if st_path.exists() else 0
    budget = 150 if total_players >= 5 else 90
    if st_lines > budget:
        bad(f"状态跟踪 {st_lines} 行，超过 {total_players} 人团预算 {budget} 行，先降级低频内容")
    else:
        ok(f"状态跟踪 {st_lines} 行，在预算 {budget} 行内")

    st = tables(st_path)
    for r in st.get("承诺与约定", []):
        if len(r) < 6:
            continue
        due = NUM.search(r[4])
        if due and "未兑现" in r[5] and cur > int(due.group(0)):
            bad(f"承诺超期未兑现：{r[0]} 答应 {r[2]}「{r[1]}」，期限 {due.group(0)}，当前 {cur:03d}")

    recap = logdir / "前情提要.md"
    recap_lines = len(recap.read_text(encoding="utf-8").splitlines()) if recap.exists() else 0
    rc = tables(recap)
    l1_budget = 50 if total_players >= 5 else 40
    l1_marker = recap.read_text(encoding="utf-8").find("## L2") if recap.exists() else -1
    l1_lines = recap.read_text(encoding="utf-8")[:l1_marker].count("\n") if l1_marker > 0 else recap_lines
    if l1_lines > l1_budget:
        bad(f"L1 索引 {l1_lines} 行，超过预算 {l1_budget} 行")

    for r in rc.get("观察区（玩家在意、但尚无咬合的事，三场无咬合即删）", []):
        if len(r) < 4:
            continue
        due = NUM.search(r[3])
        if due and cur >= int(due.group(0)):
            soft(f"观察区到期未处理：{r[0]}（到期 {due.group(0)}）——要么咬合进主线，要么删")

    for r in rc.get("未闭指针", []):
        if len(r) < 4:
            continue
        if r[3].startswith("否"):
            soft(f"指针已标不成立仍挂着：{r[0]}，删掉或说明为何保留")

    return report()


def report() -> int:
    print()
    print(f"通过 {okn} 项，提醒 {len(warn)} 项，漂移 {len(drift)} 项。")
    if drift:
        print("结论：有漂移，开局前先对账修掉。")
        return 1
    print("结论：没有硬漂移。提醒项按需处理。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
