"""打包自包含会话：只把这一场要用的东西拷出来，物理隔离其余内容。

用法：
    python tools/pack_session.py sessions/2026-11-23-rain-train-01
    python tools/pack_session.py sessions/... --out dist
    python tools/pack_session.py sessions/... --with-docs   # 额外带记忆管理/单人玩法

产物：<out>/<session_id>/ ，用 START.md 作为入口。
为什么需要它：P1 是在豆包里「打开一个文件夹」跑团，模型默认能看见整个仓库——
别的剧本的真相、别的会话的日志都会污染判断。打包后只暴露本场清单。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

START = """# 开始之前

你是这一场团的 KP。按下面顺序读，读完再开口：

1. `keeper/system-prompt.md`（你的身份与边界）
2. `keeper/_framework.md`（判定、骰源、抗嘴炮、复核）
3. `keeper/personas/{persona}.md`（本场人设）
4. `systems/{system}/system.md` → `判定.md` → `车卡规格.md`（有战斗/成长篇一并读）
5. `session/00-本次设定.md`（manifest：装载清单、禁止装载、骰源）
6. `session/状态跟踪.md` → `session/03-日志/前情提要.md`（硬事实与索引，先对账再开场）
7. `session/02-剧本/` 六件（这是剧本，不是给你复述的文本）
8. `session/01-车卡/` 参团角色卡

规矩：
- 骰值由你掷，或让玩家用 `tools/roll.py` 掷后把输出贴进来；只报数字的自掷无效。日志写明骰源。
- 本包之外的文件不在你的视野里，也不要假装知道。剧本没写的地方按规则书通例，并说明你在做通例判断。
- 判定依据只解释一次；节奏、内容不适、要方向可以协商；难度、结果、已掷骰值不可协商。
- 一场结束：写 `session/03-日志/日志-NNN.md`（含丢弃清单），更新 `状态跟踪.md`，成长落卡。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--with-docs", action="store_true")
    args = ap.parse_args()

    session = Path(args.session).resolve()
    man_path = session / "00-本次设定.md"
    if not man_path.exists():
        print(f"找不到 manifest：{man_path}")
        return 2
    man, _ = fm.read(man_path)
    sid = str(man.get("session_id") or session.name)
    system = str(man.get("规则系统") or "coc7")
    persona = str(man.get("KP人设") or "")
    if not persona:
        print("manifest 缺 KP人设，无法打包。")
        return 2

    repo = REPO
    if not (repo / "keeper" / "_framework.md").exists():
        for anc in session.parents:
            if (anc / "keeper" / "_framework.md").exists():
                repo = anc
                break
    dest = (repo / args.out / sid) if not Path(args.out).is_absolute() else Path(args.out) / sid
    if dest.exists():
        print(f"目标已存在，先删掉再打包：{dest}")
        return 2
    dest.mkdir(parents=True)

    def put(src: Path, rel: str) -> bool:
        if not src.exists():
            print(f"[跳过] 缺少 {rel}")
            return False
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True

    put(REPO / "keeper" / "system-prompt.md", "keeper/system-prompt.md")
    put(REPO / "keeper" / "_framework.md", "keeper/_framework.md")
    put(REPO / "keeper" / "personas" / f"{persona}.md", f"keeper/personas/{persona}.md")
    put(REPO / "keeper" / "roles" / "车卡向导.md", "keeper/roles/车卡向导.md")

    for name in ["system.md", "判定.md", "车卡规格.md", "战斗与理智.md", "成长.md"]:
        put(REPO / "systems" / system / name, f"systems/{system}/{name}")

    put(REPO / "tools" / "roll.py", "tools/roll.py")

    if args.with_docs:
        put(REPO / "docs" / "记忆管理.md", "docs/记忆管理.md")
        put(REPO / "docs" / "单人玩法.md", "docs/单人玩法.md")

    for item in session.iterdir():
        if item.is_dir():
            shutil.copytree(item, dest / "session" / item.name)
        elif item.is_file():
            put(item, f"session/{item.name}")

    (dest / "START.md").write_text(
        START.replace("{persona}", persona).replace("{system}", system),
        encoding="utf-8",
    )

    files = sorted(p for p in dest.rglob("*") if p.is_file())
    listing = "\n".join(f"{p.relative_to(dest).as_posix()}\t{p.stat().st_size}B" for p in files)
    (dest / "MANIFEST.txt").write_text(
        f"session_id: {sid}\n剧本: {man.get('剧本id')}\n系统: {system} {man.get('系统版本')}\n"
        f"人设: {persona}\n分级: {man.get('内容分级')}\n文件数: {len(files)}\n\n{listing}\n",
        encoding="utf-8",
    )
    print(f"已打包：{dest}")
    print(f"  文件 {len(files)} 个，入口 START.md")
    print(f"提示：这是最小运行包；本包之外的内容模型不该看见。带文档加 --with-docs。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
