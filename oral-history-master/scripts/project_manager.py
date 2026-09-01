#!/usr/bin/env python3
"""
project_manager.py · 项目初始化 / 导入 / 校验 / 进度
====================================================

每位受访人 / 每次访谈 = 一个 project：
    projects/<name>/
    ├── sources/      raw.txt(原始转写) + ingested.md(清洗后)
    ├── edit_spec.md  整理方针（Surveyor 产出，人读）
    ├── term_lock.md  执行契约（机读，Editor 每块重读）
    ├── work/         chunks/ edited/ manifest.json
    ├── output/       整理稿.md
    └── review/       对照稿.md 审阅稿.html/.docx 待核对清单.md 一致性报告.md

用法：
    python3 project_manager.py init  <name> [--projects-root DIR]
    python3 project_manager.py import <name> <transcript_file> [--move]
    python3 project_manager.py validate <name>
    python3 project_manager.py status  <name>
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import config as C

CST = timezone(timedelta(hours=8))  # Asia/Shanghai


def _projects_root(args) -> Path:
    root = Path(args.projects_root) if args.projects_root else (C.SKILL_DIR / "projects")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _read_template(name: str) -> str:
    p = C.SKILL_DIR / "templates" / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def cmd_init(args) -> int:
    proj = C.project_path(_projects_root(args), args.name)
    if proj.exists() and any(proj.iterdir()):
        print(f"⚠ 项目已存在且非空：{proj}")
        if not args.force:
            print("  用 --force 覆盖，或换个名字。")
            return 1
    C.ensure_layout(proj)

    # 写 edit_spec / term_lock 骨架（Surveyor 阶段填充）
    spec = proj / C.FILE_EDIT_SPEC
    if not spec.exists() or args.force:
        tpl = _read_template("edit_spec_reference.md")
        spec.write_text(tpl or "# 整理方针（待 Surveyor 填充）\n", encoding="utf-8")
    lock = proj / C.FILE_TERM_LOCK
    if not lock.exists() or args.force:
        tpl = _read_template("term_lock_reference.md")
        lock.write_text(tpl or "# term_lock（待 Surveyor 填充）\n", encoding="utf-8")

    # 空 manifest
    manifest = proj / C.FILE_MANIFEST
    if not manifest.exists() or args.force:
        manifest.write_text(json.dumps({
            "project": args.name,
            "created": datetime.now(CST).isoformat(timespec="seconds"),
            "pass": 1,
            "chunks": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 项目已创建：{proj}")
    print("   下一步：python3 project_manager.py import "
          f"{args.name} <转写稿文件>")
    return 0


def cmd_import(args) -> int:
    proj = C.project_path(_projects_root(args), args.name)
    if not proj.exists():
        print(f"✗ 项目不存在，先 init：{args.name}")
        return 1
    src = Path(args.transcript)
    if not src.exists():
        print(f"✗ 找不到转写稿：{src}")
        return 1
    dst = proj / C.FILE_RAW
    # 统一落成 raw.txt；docx/md 也先原样复制，ingest 再处理
    if src.suffix.lower() in {".txt", ".md"}:
        dst.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    else:
        dst = proj / "sources" / ("raw" + src.suffix.lower())
        shutil.copy2(src, dst)
    if args.move:
        try:
            src.unlink()
        except OSError:
            pass
    print(f"✅ 已导入：{dst}")
    print(f"   下一步：python3 transcript_ingest.py {args.name}")
    return 0


def cmd_validate(args) -> int:
    proj = C.project_path(_projects_root(args), args.name)
    if not proj.exists():
        print(f"✗ 项目不存在：{args.name}")
        return 1
    ok = True
    for sub in C.PROJECT_LAYOUT.values():
        if not (proj / sub).is_dir():
            print(f"✗ 缺目录：{sub}")
            ok = False
    for f in (C.FILE_EDIT_SPEC, C.FILE_TERM_LOCK, C.FILE_MANIFEST):
        if not (proj / f).exists():
            print(f"✗ 缺文件：{f}")
            ok = False
    print("✅ 结构完整" if ok else "⚠ 结构不完整（见上）")
    return 0 if ok else 1


def cmd_status(args) -> int:
    proj = C.project_path(_projects_root(args), args.name)
    mf = proj / C.FILE_MANIFEST
    if not mf.exists():
        print(f"✗ 无 manifest，项目可能未初始化：{args.name}")
        return 1
    data = json.loads(mf.read_text(encoding="utf-8"))
    chunks = data.get("chunks", [])
    done = sum(1 for c in chunks if c.get("status") == "edited")
    total = len(chunks)
    raw = proj / C.FILE_RAW
    raw_chars = len(raw.read_text(encoding="utf-8", errors="replace")) if raw.exists() else 0
    sw = C.parse_switches(proj / C.FILE_TERM_LOCK)
    print(f"📋 项目：{data.get('project')}  (Pass {data.get('pass', 1)})")
    print(f"   文类：{sw.get('genre')} · 语气词：{sw.get('fillers')}")
    print(f"   原始字数：约 {raw_chars} 字")
    print(f"   分块进度：{done}/{total} 块已整理")
    if total:
        bar = "█" * int(20 * done / total) + "░" * (20 - int(20 * done / total))
        print(f"   [{bar}] {int(100*done/total)}%")
    for c in chunks:
        flag = {"edited": "✓", "pending": "·"}.get(c.get("status"), "?")
        print(f"     {flag} {c.get('id')}  {c.get('chars', '?')}字")
    print("   审阅包：")
    for rel in (C.FILE_COMPARE, C.FILE_REVIEW_HTML, C.FILE_REVIEW_DOCX, C.FILE_FILLER):
        mark = "✓" if (proj / rel).exists() else "·"
        print(f"     {mark} {rel}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="oral-history-master 项目管理")
    ap.add_argument("--projects-root", help="projects 根目录（默认 skill/projects）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("name"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("import"); p.add_argument("name"); p.add_argument("transcript"); p.add_argument("--move", action="store_true")
    p = sub.add_parser("validate"); p.add_argument("name")
    p = sub.add_parser("status"); p.add_argument("name")

    args = ap.parse_args()
    return {
        "init": cmd_init, "import": cmd_import,
        "validate": cmd_validate, "status": cmd_status,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
