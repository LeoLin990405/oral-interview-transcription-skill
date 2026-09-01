#!/usr/bin/env python3
"""
run_pipeline.py · 确定性段编排器
================================
把"非语义"的脚本步骤串起来一条命令跑完。中间的两个语义环节
（Surveyor 定方针 / Editor 逐块整理）由主 agent 完成，不在此自动化。

    prep  <name>   ingest → glossary → chunker      （Surveyor/Editor 之前）
    check <name>   consistency → fidelity → diff → package → report （Editor 之后）

用法：
    python3 run_pipeline.py prep  <name> [--projects-root DIR] [chunker 透传参数]
    python3 run_pipeline.py check <name> [--projects-root DIR]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PREP = ["transcript_ingest.py", "glossary_extractor.py", "chunker.py"]
CHECK = ["consistency_checker.py", "fidelity_checker.py", "diff_reporter.py",
         "filler_scan.py", "package_review.py", "report.py"]


def _run(script: str, passthrough: list[str]) -> int:
    print(f"\n{'═' * 60}\n▶ {script}\n{'═' * 60}")
    r = subprocess.run([sys.executable, str(HERE / script), *passthrough])
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["prep", "check"])
    ap.add_argument("name")
    ap.add_argument("--projects-root")
    args, extra = ap.parse_known_args()

    base = [args.name] + (["--projects-root", args.projects_root] if args.projects_root else [])
    steps = PREP if args.phase == "prep" else CHECK
    # 非致命步骤（报告类不因 error 退出码中断流水线，仍要出报告）
    soft = {"fidelity_checker.py", "consistency_checker.py", "report.py"}

    worst = 0
    for s in steps:
        passthrough = base + (extra if s == "chunker.py" else [])
        rc = _run(s, passthrough)
        if rc != 0:
            worst = max(worst, rc)
            if s not in soft:
                print(f"\n✗ {s} 失败（exit {rc}），流水线中断。")
                return rc
            print(f"\n⚠ {s} 报告了问题（exit {rc}），继续生成后续报告。")

    print(f"\n{'═' * 60}")
    if args.phase == "prep":
        print("✅ prep 完成 → 接下来：Surveyor 定方针（填 term_lock）→ Editor 逐块整理 → run_pipeline.py check")
    else:
        print("✅ check 完成 → 看 review/质检总览.md；若有 error/变体残留回 Editor 返工，否则进 quality-guard。")
    return worst


if __name__ == "__main__":
    sys.exit(main())
