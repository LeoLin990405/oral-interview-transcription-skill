#!/usr/bin/env python3
"""
diff_reporter.py · 原始 vs 整理稿 逐段审阅包
============================================
按说话人轮次对齐，做字级修订，写出三份可追溯对照：

  review/对照稿.md     Markdown（删除线 + 加粗）
  review/审阅稿.html   浏览器 Word 式审阅（审阅/原文/整理切换）
  review/审阅稿.docx   Word/WPS 修订（可接受/拒绝）

用法：python3 diff_reporter.py <name> [--projects-root DIR]
"""
from __future__ import annotations

import argparse
import sys

import config as C
import review_diff as R


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--projects-root")
    args = ap.parse_args()

    proj = C.resolve(args.name, args.projects_root)
    try:
        paths = R.write_review_bundle(proj, title=args.name)
    except FileNotFoundError as e:
        sys.exit(f"✗ {e}")

    print(f"✅ 对照稿 → {paths['md']}")
    print(f"✅ 审阅稿（浏览器）→ {paths['html']}")
    print(f"✅ 审阅稿（Word 修订）→ {paths['docx']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
