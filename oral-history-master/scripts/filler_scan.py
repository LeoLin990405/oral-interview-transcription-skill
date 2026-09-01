#!/usr/bin/env python3
"""
filler_scan.py · 整理稿语气词 / 重复残留扫描
============================================
只提示、不改写。扫 work/edited 里疑似未清的 B 类噪音，写成
review/语气词残留.md，供 Editor 返工或 quality-guard 抽查。

用法：python3 filler_scan.py <name> [--projects-root DIR]
退出码始终 0（提示门，不是硬门）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import config as C

# 句末「啊/呢/吧/嘛」常有语法功能，标准档不报；加强档才报孤立填充
TRAILING_PARTICLE_RE = re.compile(r"[啊呢吧嘛](?=[。！？…\s]|$)")
# 「困难啊」里的啊有功能；只报前后都不是汉字/字母的孤立语气词
ISOLATED_FILLER_RE = re.compile(r"(?<![一-鿿A-Za-z])([嗯啊呃额唔])(?![一-鿿A-Za-z])")
ISOLATED_FILLER_STRONG_RE = re.compile(r"(?<![一-鿿A-Za-z])([嗯啊呃额唔欸诶])(?![一-鿿A-Za-z])")


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
        if ef.exists():
            yield cid, ef.read_text(encoding="utf-8")


def _hits_for(text: str, *, strong: bool) -> list[tuple[str, str]]:
    """返回 (类别, 摘录) 列表。"""
    hits: list[tuple[str, str]] = []
    phrases = C.FILLER_PHRASES_STRONG if strong else C.FILLER_PHRASES_STANDARD
    for ph in phrases:
        if ph in text:
            hits.append(("口头禅", ph))
    char_re = ISOLATED_FILLER_STRONG_RE if strong else ISOLATED_FILLER_RE
    seen = set()
    for m in char_re.finditer(text):
        ch = m.group(1)
        if ch not in seen:
            seen.add(ch)
            hits.append(("语气词", ch))
    for m in C.STUTTER_RE.finditer(text):
        hits.append(("自我重复", m.group(0)))
    if strong:
        for m in TRAILING_PARTICLE_RE.finditer(text):
            start = max(0, m.start() - 8)
            hits.append(("句末语气词（加强档）", text[start:m.end() + 1].strip()))
    return hits


def scan_project(proj: Path) -> list[tuple[str, str, str]]:
    switches = C.parse_switches(proj / C.FILE_TERM_LOCK)
    strong = "加强" in switches.get("fillers", "")
    rows: list[tuple[str, str, str]] = []
    for cid, text in _edited_in_order(proj):
        # 扫描前剥 〔说明〕，避免把注释里的「那个」当残留
        body = re.sub(r"〔[^〕]*〕", "", text)
        for kind, excerpt in _hits_for(body, strong=strong):
            rows.append((cid, kind, excerpt))
    return rows


def render_report(name: str, rows: list[tuple[str, str, str]], *, strong: bool) -> str:
    level = "加强" if strong else "标准"
    out = [
        "# 语气词 / 重复残留",
        "",
        f"> 项目 `{name}` · 扫描档：**{level}**。本报告只提示，不改字。",
        "> 有语义功能的「那个项目 / 困难啊 / 对，就是这个意思」应保留；",
        "> 无语义填充、口吃重复、倾听性「对对对」应在整理稿中清掉。",
        "",
        f"共 {len(rows)} 处疑似残留。",
        "",
    ]
    if not rows:
        out.append("- 未扫到常见语气词或自我重复。仍须人工确认没有漏清、也没有误删。")
        return "\n".join(out) + "\n"
    out += ["| 块 | 类别 | 摘录 |", "|---|---|---|"]
    for cid, kind, excerpt in rows:
        clipped = excerpt.replace("|", "\\|")
        if len(clipped) > 40:
            clipped = clipped[:40] + "…"
        out.append(f"| {cid} | {kind} | {clipped} |")
    out += [
        "",
        "## 怎么用",
        "- Editor：回对应块判断是残留噪音还是 A 类保护，该删则删、该留则留。",
        "- quality-guard：抽查这些位置，确认没有把功能性语气词误报成噪音。",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--projects-root")
    args = ap.parse_args()

    proj = C.resolve(args.name, args.projects_root)
    if not (proj / C.PROJECT_LAYOUT["edited"]).exists():
        sys.exit(f"✗ 项目无 work/edited：{args.name}")

    switches = C.parse_switches(proj / C.FILE_TERM_LOCK)
    strong = "加强" in switches.get("fillers", "")
    rows = scan_project(proj)
    dst = proj / C.FILE_FILLER
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(render_report(args.name, rows, strong=strong), encoding="utf-8")
    print(f"✅ 语气词残留 → {dst}（{len(rows)} 处提示，档={('加强' if strong else '标准')}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
