"""可验证骰值：输出带时间戳与种子，结果可粘贴进日志、可事后复算。

用法：
    python tools/roll.py 1d100 --label 侦查
    python tools/roll.py 1d100 --label 侦查 --bonus 1
    python tools/roll.py 1d100 --label 暗投 --penalty 1
    python tools/roll.py 2d6+3 --label 伤害
    python tools/roll.py 1d100 --seed 123456        # 复算同一次结果

输出两行：人读的一行 + 可粘贴的一行（含种子）。粘贴记录进日志即视为有效骰值。
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from datetime import datetime

SPEC = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$", re.I)


def parse(spec: str) -> tuple[int, int, int]:
    m = SPEC.match(spec)
    if not m:
        raise ValueError(f"看不懂的骰式：{spec}（示例：1d100 / 2d6+3 / d20）")
    n = int(m.group(1) or 1)
    sides = int(m.group(2))
    mod = int((m.group(3) or "+0").replace(" ", ""))
    if n < 1 or n > 100 or sides < 2:
        raise ValueError(f"骰式范围不合法：{spec}")
    return n, sides, mod


def roll_percentile(rng: random.random, bonus: int, penalty: int) -> tuple[int, int]:
    """COC 奖励/惩罚骰：个位一次，十位掷 1+奖励+惩罚 次，奖励取小、惩罚取大。"""
    units = rng.randint(0, 9)
    picks = [rng.randint(0, 9) for _ in range(1 + bonus + penalty)]
    tens = None
    if bonus:
        tens = min(picks[: 1 + bonus])
    if penalty:
        tens = max(picks[-1 - penalty:])
    if tens is None:
        tens = picks[0]
    value = tens * 10 + units
    return (100 if value == 0 else value), len(picks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="骰式，如 1d100 / 2d6+3")
    ap.add_argument("--label", default="", help="这次判定是什么，如「侦查」「伤害」")
    ap.add_argument("--bonus", type=int, default=0, help="奖励骰个数（仅 d100 有意义）")
    ap.add_argument("--penalty", type=int, default=0, help="惩罚骰个数（仅 d100 有意义）")
    ap.add_argument("--seed", type=int, default=None, help="指定种子以复算历史骰值")
    args = ap.parse_args()

    try:
        n, sides, mod = parse(args.spec)
    except ValueError as exc:
        print(exc)
        return 2
    if (args.bonus or args.penalty) and not (n == 1 and sides == 100):
        print("奖励/惩罚骰只用于 1d100。")
        return 2

    seed = args.seed if args.seed is not None else random.randrange(1, 10 ** 9)
    rng = random.Random(seed)
    parts: list[int] = []
    if args.bonus or args.penalty:
        total, extra = roll_percentile(rng, args.bonus, args.penalty)
    else:
        for _ in range(n):
            parts.append(rng.randint(1, sides))
        total = sum(parts) + mod

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    label = args.label or "未命名"
    detail = "+".join(str(p) for p in parts) if parts else f"奖励{args.bonus}/惩罚{args.penalty}"
    if mod:
        detail += f"{mod:+d}"
    print(f"[{stamp}] {label} | {args.spec} | {detail} | → {total}")
    print(f"可粘贴：骰源：tools/roll.py｜{stamp}｜{label}｜{args.spec}({detail}) = {total}｜seed {seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
