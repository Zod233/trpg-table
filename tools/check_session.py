"""开局前预检：机械校验一个会话文件夹是否可跑。

用法：
    python tools/check_session.py sessions/2026-11-23-rain-train-01

退出码 0 = 全部通过（提醒不算失败），1 = 有失败项，不得开局。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm  # noqa: E402

REQUIRED = [
    "session_id", "剧本id", "剧本形态", "规则系统", "系统版本", "KP人设",
    "车卡生成法", "成长方式", "内容分级", "骰源", "玩家数", "参团角色",
    "当前场次", "开始日期", "装载清单",
]
FORMES = {"线性", "沙盒", "调查", "混合"}
RATINGS = {"L0", "L1", "L2", "L3"}

ok_count = 0
fail: list[str] = []
warn: list[str] = []


def ok(msg: str) -> None:
    global ok_count
    ok_count += 1
    print(f"[通过] {msg}")


def bad(msg: str) -> None:
    fail.append(msg)
    print(f"[失败] {msg}")


def soft(msg: str) -> None:
    warn.append(msg)
    print(f"[提醒] {msg}")


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python tools/check_session.py <会话文件夹>")
        return 2
    session = Path(sys.argv[1]).resolve()
    if not session.is_dir():
        print(f"找不到会话文件夹：{session}")
        return 2
    if session.name == "_template":
        print("_template 是模板本身，没有具体剧本与角色，不参与预检。")
        return 2

    repo = session.parent.parent
    if not (repo / "keeper" / "_framework.md").exists():
        repo = None
        for anc in session.parents:
            if (anc / "keeper" / "_framework.md").exists():
                repo = anc
                break
    if repo is None:
        print("[失败] 会话不在仓库内：找不到 keeper/_framework.md，无法解析系统包与提示词路径。")
        print("结论：不可开局。把会话放在 <仓库>/sessions/ 下再预检。")
        return 1
    man_path = session / "00-本次设定.md"
    if not man_path.exists():
        bad("缺少 00-本次设定.md（manifest）")
        return 1
    man, _ = fm.read(man_path)

    for key in REQUIRED:
        value = man.get(key)
        if not value or (isinstance(value, str) and value.strip() == ""):
            bad(f"manifest 缺少字段：{key}")
        elif isinstance(value, str) and ("<" in value or ">" in value):
            bad(f"manifest 字段仍有占位符：{key} = {value}")
    ok("manifest 必填字段齐全")

    forme = man.get("剧本形态")
    if isinstance(forme, str) and forme not in FORMES:
        bad(f"剧本形态不合法：{forme}（应为 {'/'.join(sorted(FORMES))}）")
    rating = man.get("内容分级")
    if isinstance(rating, str) and rating not in RATINGS:
        bad(f"内容分级不合法：{rating}（应为 L0–L3）")

    dice = str(man.get("骰源") or "")
    if not any(k in dice for k in ("平台", "外部", "KP自掷", "roll.py")):
        bad(f"骰源不合法：{dice}（应为 平台骰具 / 外部骰具或 tools/roll.py / KP 自掷）")
    elif "KP自掷" in dice:
        soft(f"骰源为 KP 自掷（未审计）：日志里每场都要标「骰源：KP自掷」，方便日后回溯无法复核的判定")
    try:
        players = int(str(man.get("玩家数") or "").strip())
        if players < 1:
            raise ValueError
    except ValueError:
        players = 0
        bad(f"玩家数不合法：{man.get('玩家数')}（应为正整数）")

    sysid = man.get("规则系统")
    sysver = man.get("系统版本")
    sys_file = repo / "systems" / str(sysid) / "system.md"
    if not sys_file.exists():
        bad(f"规则系统包不存在：systems/{sysid}/system.md")
    else:
        sysfm, _ = fm.read(sys_file)
        if str(sysver) != str(sysfm.get("版本")):
            bad(f"版本不一致：manifest 写 {sysver}，systems/{sysid}/system.md 写 {sysfm.get('版本')}")
        else:
            ok(f"规则系统 {sysid} 版本 {sysver} 与包一致")

    persona = man.get("KP人设")
    persona_path = repo / "keeper" / "personas" / f"{persona}.md"
    if not persona_path.exists():
        bad(f"KP 人设不存在：keeper/personas/{persona}.md")
    else:
        ok(f"KP 人设存在：{persona}")

    load = fm.as_list(man.get("装载清单"))
    if not load:
        bad("装载清单为空")
    else:
        before = len(fail)
        for item in load:
            if "<" in item or ">" in item:
                bad(f"装载清单仍有占位符：{item}")
                continue
            if item.startswith(".."):
                bad(f"装载清单出现跨会话路径：{item}")
                continue
            cand_session = session / item
            cand_repo = repo / item
            if not (cand_session.exists() or cand_repo.exists()):
                bad(f"装载清单里的路径不存在：{item}")
        if len(fail) == before:
            ok(f"装载清单共 {len(load)} 项，路径均可解析")

    scen_id = str(man.get("剧本id"))
    scen_dir = session / "02-剧本"
    scen_files = [p for p in scen_dir.glob("*.md")] if scen_dir.exists() else []
    if not scen_files:
        bad("02-剧本/ 为空，没有剧本副本")
    else:
        brief = None
        for p in scen_files:
            if p.name.startswith("00"):
                brief = p
        if brief is None:
            soft("02-剧本/ 里没有 00-剧本概览.md，无法校验剧本声明")
        else:
            bf, _ = fm.read(brief)
            if str(bf.get("id")) != scen_id:
                bad(f"剧本 id 不一致：manifest 写 {scen_id}，副本概览写 {bf.get('id')}")
            if str(bf.get("规则系统")) != str(sysid):
                bad(f"剧本声明的规则系统 {bf.get('规则系统')} 与 manifest {sysid} 不一致")
            if str(bf.get("系统版本")) != str(sysver):
                bad(f"剧本声明的系统版本 {bf.get('系统版本')} 与 manifest {sysver} 不一致")
            solo = str(bf.get("单人可跑") or "")
            if players == 1:
                if solo.startswith("否"):
                    bad("剧本标注「单人可跑：否」，但本场玩家数为 1")
                elif solo and not solo.startswith("是"):
                    soft(f"剧本单人可跑标记为「{solo}」，开局前按 docs/单人玩法.md 适配")
            if not str(bf.get("来源") or ""):
                soft("剧本概览缺「来源」字段：分了级但没写来源，日后无法追溯（原创写「原创」，外部模组写作者与出处）")
            ok(f"剧本副本 {scen_id} 声明与 manifest 一致")

    cards = sorted((session / "01-车卡").glob("*.md")) if (session / "01-车卡").exists() else []
    cards = [c for c in cards if not c.name.startswith("_")]
    if not cards:
        bad("01-车卡/ 里没有角色卡")
    listed = fm.as_list(man.get("参团角色"))
    before = len(fail)
    for card in cards:
        cfm, _ = fm.read(card)
        cid = str(cfm.get("角色id") or card.stem)
        if cfm.get("审核状态") != "通过":
            bad(f"角色 {cid} 审核未通过：{cfm.get('审核状态')}")
        if str(cfm.get("规则系统")) != str(sysid):
            bad(f"角色 {cid} 属于 {cfm.get('规则系统')}，与本场 {sysid} 不符")
        if listed and cid not in listed:
            bad(f"角色 {cid} 未登记在 manifest 的参团角色里")
    if cards and len(fail) == before:
        ok(f"角色卡共 {len(cards)} 张，均已过审且系统一致")
    if players and len(cards) != players:
        bad(f"玩家数写 {players}，但 01-车卡/ 里有 {len(cards)} 张卡，人数对不上")

    for name in ["状态跟踪.md", "04-KP私有.md", "03-日志/前情提要.md"]:
        if not (session / name).exists():
            bad(f"缺少必备文件：{name}")
    if (session / "05-玩家私有").exists():
        ok("05-玩家私有/ 存在")
    else:
        soft("缺少 05-玩家私有/，多人私密信息无处分流")

    ep = str(man.get("当前场次") or "").zfill(3)
    log_path = session / "03-日志" / f"日志-{ep}.md"
    if log_path.exists():
        ok(f"本场日志存在：03-日志/日志-{ep}.md")
    else:
        soft(f"03-日志/日志-{ep}.md 尚未创建（开局前建好即可）")

    print()
    print(f"通过 {ok_count} 项，提醒 {len(warn)} 项，失败 {len(fail)} 项。")
    if fail:
        print("结论：不可开局。先修掉失败项。")
        return 1
    print("结论：可以开局。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
