"""按模板生成一个可跑的会话文件夹。

用法：
    python tools/new_session.py --scenario rain-train --system coc7 \
        --persona 温柔引导者 --characters lin-yan --rating L1

会做四件事：
1. 复制 sessions/_template → sessions/<日期>-<剧本id>-NN（NN 自动递增）
2. 把 scenarios/<剧本id>/ 的剧本复制进 02-剧本/
3. 把 characters/<角色id>/角色卡.md 复制进 01-车卡/，并生成对应的玩家私有文件
4. 回填 manifest：id、系统版本、人设、角色、场次、日期、分级
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def build_manifest(template: str, args, sys_version: str, cards: list[tuple[str, str]], index: int) -> str:
    text = template
    for key, value in [
        ("剧本id", args.scenario),
        ("剧本形态", args.forme),
        ("规则系统", args.system),
        ("系统版本", sys_version),
        ("KP人设", args.persona),
        ("车卡生成法", args.cardgen),
        ("成长方式", args.growth),
        ("内容分级", args.rating),
        ("骰源", args.dice),
        ("玩家数", str(len(cards) or 1)),
        ("当前场次", "001"),
        ("开始日期", args.date),
        ("session_id", f"{args.date}-{args.scenario}-{index:02d}"),
        ("状态", "进行中"),
    ]:
        text = fm.set_field(text, key, value)

    # 参团角色：把空列表换成块状列表
    lines = text.splitlines()
    new_lines: list[str] = []
    inserted = False
    for line in lines:
        if line.strip() == "参团角色: []":
            new_lines.append("参团角色:")
            for cid, _ in cards:
                new_lines.append(f"  - {cid}")
            inserted = True
        else:
            new_lines.append(line)
    if not inserted:
        text = "\n".join(new_lines)
        text = fm.set_field(text, "参团角色", ", ".join(cid for cid, _ in cards))
    else:
        text = "\n".join(new_lines)

    # 装载清单里的系统、人设、日志占位
    text = text.replace("systems/coc7/", f"systems/{args.system}/")
    text = text.replace("keeper/personas/<人设>.md", f"keeper/personas/{args.persona}.md")
    text = text.replace("03-日志/日志-<当前场次>.md", "03-日志/日志-001.md")

    # 正文里的占位符
    for old, new in [
        ("<剧本id>", args.scenario),
        ("<规则系统>", args.system),
        ("<系统>", args.system),
        ("<人设>", args.persona),
    ]:
        text = text.replace(old, new)

    # 参团角色表
    rows = "\n".join(
        f"| 玩家 | {cid} | {cid} | {state} | {state} |" for cid, state in cards
    )
    text = text.replace(
        "| 玩家 | 角色 | 角色id | 数值审核 | 叙事审核 |\n| --- | --- | --- | --- | --- |\n|  |  |  | 通过 / 退回 | 通过 / 退回 |",
        "| 玩家 | 角色 | 角色id | 数值审核 | 叙事审核 |\n| --- | --- | --- | --- | --- |\n" + rows,
    )
    return text if text.endswith("\n") else text + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, help="剧本 id，对应 scenarios/<id>/")
    ap.add_argument("--system", default="coc7")
    ap.add_argument("--persona", default="温柔引导者")
    ap.add_argument("--characters", default="", help="角色 id，逗号分隔")
    ap.add_argument("--cardgen", default="掷骰法")
    ap.add_argument("--growth", default="技能成长检定")
    ap.add_argument("--rating", default="L1")
    ap.add_argument("--dice", default="KP自掷", help="平台骰具 / 外部骰具或 tools/roll.py / KP自掷")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--index", type=int, default=0, help="0 = 自动取下一个序号")
    ap.add_argument("--local", action="store_true", help="会话放进 sessions/local/（本地模组，不进仓库）")
    args = ap.parse_args()

    scenario_dir = REPO / "scenarios" / args.scenario
    if not scenario_dir.is_dir():
        # 支持 scenarios/local/<id> 这种本地模组目录（不进仓库，见 .gitignore）
        scenario_dir = REPO / "scenarios" / "local" / args.scenario
    if not scenario_dir.is_dir():
        print(f"找不到剧本：{scenario_dir}")
        return 2
    args.scenario = scenario_dir.name
    sys_file = REPO / "systems" / args.system / "system.md"
    if not sys_file.exists():
        print(f"找不到规则系统：{sys_file}")
        return 2
    sysfm, _ = fm.read(sys_file)
    sys_version = str(sysfm.get("版本") or "1.0")

    brief = scenario_dir / "00-剧本概览.md"
    args.forme = ""
    if brief.exists():
        bf, _ = fm.read(brief)
        args.forme = str(bf.get("形态") or "")
    if not args.forme:
        print("剧本概览缺少 形态 字段（线性 / 沙盒 / 调查 / 混合），先补上再开团。")
        return 2

    persona_file = REPO / "keeper" / "personas" / f"{args.persona}.md"
    if not persona_file.exists():
        print(f"找不到 KP 人设：{persona_file}")
        return 2

    cards: list[tuple[str, str]] = []
    for cid in [c.strip() for c in args.characters.split(",") if c.strip()]:
        card = REPO / "characters" / cid / "角色卡.md"
        if not card.exists():
            print(f"找不到角色卡：{card}")
            return 2
        cfm, _ = fm.read(card)
        if cfm.get("审核状态") != "通过":
            print(f"角色 {cid} 的审核状态是「{cfm.get('审核状态')}」，未通过不得进场。")
            return 2
        cards.append((cid, str(cfm.get("审核状态"))))

    base = (REPO / "sessions" / "local") if args.local else (REPO / "sessions")
    if args.local:
        base.mkdir(parents=True, exist_ok=True)
    if args.index:
        index = args.index
    else:
        index = 1
        while (base / f"{args.date}-{args.scenario}-{index:02d}").exists():
            index += 1
    session = base / f"{args.date}-{args.scenario}-{index:02d}"
    if session.exists():
        print(f"会话已存在：{session}")
        return 2

    shutil.copytree(REPO / "sessions" / "_template", session)

    scen_copy = session / "02-剧本"
    for item in scenario_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, scen_copy / item.name)

    for cid, _ in cards:
        shutil.copy2(REPO / "characters" / cid / "角色卡.md", session / "01-车卡" / f"{cid}.md")
        priv = session / "05-玩家私有" / f"{cid}.md"
        tpl = session / "05-玩家私有" / "_模板.md"
        if tpl.exists():
            content = tpl.read_text(encoding="utf-8").replace("<角色名>", cid)
            priv.write_text(content, encoding="utf-8")
            tpl.unlink()

    man = session / "00-本次设定.md"
    tpl_text = man.read_text(encoding="utf-8")
    man.write_text(build_manifest(tpl_text, args, sys_version, cards, index), encoding="utf-8")

    print(f"已生成：{session}")
    print(f"  剧本：{args.scenario}  系统：{args.system} v{sys_version}  人设：{args.persona}  分级：{args.rating}")
    print(f"  角色：{len(cards)} 张" + ("（" + "、".join(c for c, _ in cards) + "）" if cards else ""))
    print(f"下一步：python tools/check_session.py \"{session}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
