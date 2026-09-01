#!/usr/bin/env python3
"""
package_review.py · 拼接成品 + 待核对清单
==========================================
流水线末端：把逐块整理结果拼成整理稿，并汇总所有 ⚠ 待核对点。
配合 diff_reporter.py（对照稿）+ consistency_checker.py（一致性）+
fidelity_checker.py（忠实度）构成完整的"人工复核包"。

产出：
  output/整理稿.md        清洁阅读版（剥掉 〔说明〕，保留 ⚠ 提示未核实处）
  review/待核对清单.md     所有 ⚠ 逐条汇总（带块号 + 上下文），交人工 / 对录音

用法：python3 package_review.py <name> [--projects-root DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import config as C

NOTE_RE = re.compile(r"〔[^〕]*〕")
SENT_SPLIT = re.compile(rf"(?<=[{C.SENT_ENDINGS}])")


def delivery_banner(genre: str, n_todo: int) -> str:
    """整理稿页首提醒：口述史要签字，播客 / 通用访谈改发布前核对。"""
    if C.is_oral_genre(genre):
        return (
            f"> ⚠ 此稿为口述史整理稿（Pass 1），含 {n_todo} 处 `⚠` 待核对，"
            "**须经受访人审阅签字方可使用**。\n"
            "> 书面化（Pass 2）请另起流程，见 workflows/pass2-bookify.md。\n"
        )
    return (
        f"> 此稿为{genre}整理稿（Pass 1 · 去口语化），含 {n_todo} 处 `⚠` 待核对。\n"
        "> 发布前请主持人 / 嘉宾核对专名与事实；书面化（Pass 2）见 workflows/pass2-bookify.md。\n"
    )


def _edited_in_order(proj: Path):
    mf = proj / C.FILE_MANIFEST
    ids = []
    if mf.exists():
        ids = [c["id"] for c in json.loads(mf.read_text(encoding="utf-8")).get("chunks", [])]
    if not ids:
        ids = [p.stem.replace(".edited", "") for p in
               sorted((proj / C.PROJECT_LAYOUT["edited"]).glob("*.edited.md"))]
    for cid in ids:
        ef = proj / C.PROJECT_LAYOUT["edited"] / f"{cid}.edited.md"
        yield cid, (ef.read_text(encoding="utf-8").strip() if ef.exists() else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--projects-root")
    args = ap.parse_args()

    proj = C.resolve(args.name, args.projects_root)
    if not (proj / C.PROJECT_LAYOUT["edited"]).exists():
        sys.exit(f"✗ 项目无 work/edited：{args.name}")

    switches = C.parse_switches(proj / C.FILE_TERM_LOCK)
    genre = switches.get("genre", "口述史")

    clean_parts, todo = [], []
    missing = 0
    for cid, text in _edited_in_order(proj):
        if text is None:
            missing += 1
            clean_parts.append(f"〔{cid} 尚未整理〕")
            continue
        # 待核对：含 ⚠ 的句子
        for sent in SENT_SPLIT.split(text):
            if C.MARK_UNCERTAIN in sent and sent.strip():
                todo.append((cid, sent.strip()))
        # 清洁阅读版：去 〔说明〕，留 ⚠
        clean_parts.append(NOTE_RE.sub("", text))

    clean = "\n\n".join(clean_parts)
    clean = re.sub(r"[ \t]+", " ", clean)
    out_clean = proj / C.FILE_CLEAN
    out_clean.parent.mkdir(parents=True, exist_ok=True)
    banner = delivery_banner(genre, len(todo))
    out_clean.write_text(
        "# 整理稿（Pass 1 · 去口语化）\n\n"
        + banner + "\n"
        + clean + "\n", encoding="utf-8")

    todo_md = ["# 待核对清单", "",
               f"> 共 {len(todo)} 处。多为人名 / 机构 / 专名 / 同音疑似转写错，"
               "请对照录音或原始材料核定，再回填 term_lock.md 并重跑一致性校验。", ""]
    for cid, sent in todo:
        todo_md.append(f"- **[{cid}]** {sent}")
    if not todo:
        todo_md.append("- ✅ 无 ⚠ 标记（或尚未整理）。")
    (proj / C.FILE_TODO).write_text("\n".join(todo_md), encoding="utf-8")

    print(f"✅ 整理稿 → {out_clean}")
    print(f"✅ 待核对清单 → {proj / C.FILE_TODO}（{len(todo)} 处 ⚠）")
    if missing:
        print(f"⚠ 还有 {missing} 块未整理，整理稿不完整。")
    print("   复核包还需：diff_reporter.py（对照/审阅稿）/ filler_scan.py / consistency_checker.py / fidelity_checker.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
