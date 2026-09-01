#!/usr/bin/env python3
"""
transcript_ingest.py · 转写稿清洗 / 说话人分离 / 格式归一
========================================================
把杂乱的录音转写稿整理成规范的 ingested.md，供 Surveyor 通读、chunker 分块。
兼容讯飞听见 / 腾讯会议 / 通义听悟 等常见 ASR 导出格式。

只做"确定性预处理"，不做任何去口语化（那是 Editor 的活）：
  · 全角/半角、空白、换行归一
  · 识别多种说话人格式 → 统一成 【受访人】/【采访人】/【主持】/【嘉宾】 块；合并连续同说话人
  · 多种时间戳格式 → 行首 〔时间 hh:mm:ss〕 锚点（供日后对录音）
  · 副语言标记（笑/停顿/掌声…）原样保留；[听不清]/[inaudible] → 【录音不清】
  · 不删一个字、不改一个词

用法：python3 transcript_ingest.py <name> [--projects-root DIR]
输入：<proj>/sources/raw.{txt,md,docx,xlsx}
输出：<proj>/sources/ingested.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import config as C

# 时间戳：[hh:mm:ss] / [hh:mm:ss.mmm] / (mm:ss) / 【hh:mm:ss】 / 裸 mm:ss
TS_RE = re.compile(r"^[\[\(（【]?\s*(\d{1,2}:\d{2}(?::\d{2})?)(?:[.,]\d{1,3})?\s*[\]\)）】]?")

# 显式角色标签（强信号）
ROLE_RE = re.compile(
    r"^\s*(?P<sp>"
    r"受访(?:人|者)[A-Za-z甲乙丙]?|采访(?:人|者)|访谈(?:人|者)|被采访者|主持人|主持|主播|嘉宾|记者|提问者|"
    r"问|答|Q|A|Host|Guest|"
    r"(?:说话人|发言人)\s*[0-9A-Za-z一二三四五六七八九十]+|Speaker\s*\d+|S\d+"
    r")\s*[:：]\s*"
)
# 姓名（角色）：  形式，如 "李某某（受访人）："
NAME_ROLE_RE = re.compile(r"^\s*[一-鿿A-Za-z·]{2,8}\s*[（(]\s*(?P<role>受访[人者]?|采访[人者]?|被采访者|主持人|主持|主播|嘉宾|记者)\s*[)）]\s*[:：]\s*")
# 兜底：短姓名 +（可选称谓）+ 冒号
NAME_RE = re.compile(r"^\s*(?P<sp>[一-鿿]{2,4}(?:先生|女士|老师|院士|所长|教授)?)\s*[:：]\s*")

CANON = {
    "受访人": "受访人", "受访者": "受访人", "被采访者": "受访人", "答": "受访人", "A": "受访人",
    "采访人": "采访人", "采访者": "采访人", "访谈人": "采访人", "访谈者": "采访人",
    "主持人": "采访人", "记者": "采访人", "提问者": "采访人", "问": "采访人", "Q": "采访人",
    "主持": "主持", "主播": "主持", "Host": "主持",
    "嘉宾": "嘉宾", "Guest": "嘉宾",
}
INAUDIBLE_RE = re.compile(r"[（(\[【]\s*(?:听不清|不清|inaudible|无法辨认|听不出)\s*[)）\]】]", re.I)


def _read_raw(proj: Path) -> str:
    src_dir = proj / "sources"
    for ext in (".txt", ".md"):
        f = src_dir / f"raw{ext}"
        if f.exists():
            return f.read_text(encoding="utf-8", errors="replace")
    docx = src_dir / "raw.docx"
    if docx.exists():
        try:
            from docx import Document
        except ImportError:
            sys.exit("✗ 需要 python-docx 读取 .docx：pip install python-docx")
        return "\n".join(p.text for p in Document(str(docx)).paragraphs)
    xlsx = src_dir / "raw.xlsx"
    if xlsx.exists():
        try:
            import openpyxl
        except ImportError:
            sys.exit("✗ 需要 openpyxl 读取 .xlsx：pip install openpyxl")
        wb = openpyxl.load_workbook(str(xlsx), read_only=True)
        rows = []
        for ws in wb.worksheets:
            for r in ws.iter_rows(values_only=True):
                rows.append(" ".join(str(c) for c in r if c is not None))
        return "\n".join(rows)
    sys.exit(f"✗ 找不到 sources/raw.*，先 import：{proj.name}")


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("　", " ")
    text = INAUDIBLE_RE.sub("【录音不清】", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_speaker(line: str):
    """返回 (规范说话人 or None, 去掉标签后的剩余文本)。"""
    m = NAME_ROLE_RE.match(line)
    if m:
        role = m.group("role")
        if role.startswith("受访") or role == "被采访者":
            sp = "受访人"
        elif role.startswith("采访") or role in ("主持人", "记者"):
            sp = "采访人"
        elif role in ("主持", "主播"):
            sp = "主持"
        elif role == "嘉宾":
            sp = "嘉宾"
        else:
            sp = CANON.get(role, "受访人")
        return sp, line[m.end():].strip()
    m = ROLE_RE.match(line)
    if m:
        sp = m.group("sp").strip()
        return CANON.get(sp, sp), line[m.end():].strip()
    m = NAME_RE.match(line)
    if m:
        sp = m.group("sp").strip()
        return CANON.get(sp, sp), line[m.end():].strip()
    return None, line


def _segment(text: str) -> list[str]:
    out: list[tuple[str | None, str]] = []
    cur_sp: str | None = None
    buf: list[str] = []

    def flush():
        if buf:
            body = " ".join(s.strip() for s in buf if s.strip())
            if body:
                out.append((cur_sp, body))
        buf.clear()

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        ts = TS_RE.match(line)
        ts_tag = ""
        if ts:
            ts_tag = f"〔时间 {ts.group(1)}〕"
            line = line[ts.end():].strip()
        sp, rest = _detect_speaker(line)
        if sp is not None:
            flush()
            cur_sp = sp
            rest = (ts_tag + rest) if ts_tag else rest
            if rest:
                buf.append(rest)
        else:
            buf.append((ts_tag + line) if ts_tag else line)
    flush()

    # 合并连续同说话人块
    merged: list[tuple[str | None, str]] = []
    for sp, body in out:
        if merged and merged[-1][0] == sp:
            merged[-1] = (sp, merged[-1][1] + " " + body)
        else:
            merged.append((sp, body))
    return [f"{('【' + sp + '】') if sp else ''}{body}" for sp, body in merged]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--projects-root")
    args = ap.parse_args()

    proj = C.resolve(args.name, args.projects_root)
    if not proj.exists():
        sys.exit(f"✗ 项目不存在：{args.name}")

    raw = _read_raw(proj)
    blocks = _segment(_normalize(raw))
    has_speakers = any(b.startswith("【") for b in blocks)

    md = ["# 归一稿（ingested）", "",
          f"> 原始字数约 {len(raw)} 字；切出 {len(blocks)} 个语段。"
          f"{'识别到说话人轮次。' if has_speakers else '未识别到说话人标签，按段落保留。'}",
          "> ⚠ 本文件只做格式归一与说话人分离，未做任何去口语化；副语言标记（笑/停顿等）已保留。",
          ""]
    md.extend(f"{b}\n" for b in blocks)

    out = proj / C.FILE_INGESTED
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"✅ 归一完成：{out}")
    print(f"   语段数 {len(blocks)}，说话人分离：{'是' if has_speakers else '否（无标签）'}")
    print(f"   下一步：python3 glossary_extractor.py {args.name}  → 再 chunker.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
