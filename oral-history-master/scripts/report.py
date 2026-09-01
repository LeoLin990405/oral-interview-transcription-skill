#!/usr/bin/env python3
"""
report.py · 质检总览看板
========================
把分散的检查结果汇成一页 `review/质检总览.md`：进度 + 一致性 + 忠实度 + ⚠ 数
+ 交付前判定。在 consistency_checker / fidelity_checker / package_review 之后跑。

用法：python3 report.py <name> [--projects-root DIR]
退出码：可进 QA 门 → 0；需返工 → 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import config as C


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--projects-root")
    args = ap.parse_args()

    proj = C.resolve(args.name, args.projects_root)
    if not proj.exists():
        sys.exit(f"✗ 项目不存在：{args.name}")

    # 进度
    mf = json.loads(_read(proj / C.FILE_MANIFEST) or "{}")
    chunks = mf.get("chunks", [])
    total = len(chunks)
    done = sum(1 for c in chunks if c.get("status") == "edited")

    # 一致性
    cons = _read(proj / C.FILE_CONSISTENCY)
    cons_ok = "未发现变体残留" in cons
    cons_bad = cons.count("❌")
    cons_line = "✅ 术语全篇一致" if cons_ok else (f"❌ {cons_bad} 处变体未统一" if cons_bad else "· 未生成（先跑 consistency_checker）")

    # 忠实度
    fid = _read(proj / "review" / "忠实度报告.md")
    m = re.search(r"结果：(\d+) error · (\d+) warning", fid)
    fid_err = int(m.group(1)) if m else -1
    fid_warn = int(m.group(2)) if m else -1
    if fid_err < 0:
        fid_line = "· 未生成（先跑 fidelity_checker）"
    else:
        fid_line = f"{'✅' if fid_err == 0 else '❌'} {fid_err} error · {fid_warn} warning"

    # 待核对
    todo = _read(proj / C.FILE_TODO)
    warn_cnt = len(re.findall(r"^- \*\*\[", todo, re.M))

    switches = C.parse_switches(proj / C.FILE_TERM_LOCK)
    genre = switches.get("genre", "口述史")
    next_hint = (
        "通过后提醒受访人签字。"
        if C.is_oral_genre(genre) else
        "通过后请主持 / 嘉宾核专名与事实。"
    )
    html_ok = (proj / C.FILE_REVIEW_HTML).exists()
    docx_ok = (proj / C.FILE_REVIEW_DOCX).exists()
    md_ok = (proj / C.FILE_COMPARE).exists()
    pack = "✅ 齐" if html_ok and docx_ok and md_ok else "⚠ 缺 " + "、".join(
        name for name, ok in (("对照稿.md", md_ok), ("审阅稿.html", html_ok), ("审阅稿.docx", docx_ok)) if not ok
    )

    # 判定
    ready = (done == total and total > 0 and cons_ok and fid_err == 0)
    bar = ("█" * int(20 * done / total) + "░" * (20 - int(20 * done / total))) if total else ""

    out = [
        f"# 质检总览 · {args.name}", "",
        f"- **文类**：{genre} · 语气词 {switches.get('fillers', '标准')}",
        f"- **整理进度**：{done}/{total} 块  `{bar}`",
        f"- **术语一致性**：{cons_line}",
        f"- **忠实度（字数比硬门）**：{fid_line}",
        f"- **⚠ 待核对**：{warn_cnt} 处（人名/专名/数字，对录音核定后回填 term_lock 重跑）",
        f"- **审阅包**：{pack} · `对照稿.md` / `审阅稿.html` / `审阅稿.docx`",
        f"- **语气词残留**：见 `review/语气词残留.md`（提示门，非硬门）",
        f"- **忠实度 warning**：{max(fid_warn,0)} 处（新增数字/专名、不确定删除 → 交 quality-guard 逐条审）",
        "",
        "## 交付前判定",
        ("✅ **可进 QA 门**：进度完成、术语一致、字数比无 error。"
         f"下一步用 `oral-history-quality-guard` 对照原文逐段审忠实度 warning + ⚠，{next_hint}"
         if ready else
         "❌ **需返工**：" + "；".join(
             ([] if done == total and total else [f"整理未完成（{done}/{total}）"])
             + ([] if cons_ok else ["术语变体未统一"])
             + ([] if fid_err == 0 else [f"忠实度 {fid_err} 个 error"]))),
        "",
        "> 本看板汇总机械检查；语义忠实最终由 quality-guard 人工/Agent 对照原文确认。",
    ]
    dst = proj / "review" / "质检总览.md"
    dst.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"\n→ {dst}")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
