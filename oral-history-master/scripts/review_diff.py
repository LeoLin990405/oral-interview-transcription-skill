"""
review_diff.py · 逐段字级修订（对照稿 / HTML 审阅 / Word 修订）
==============================================================
脚本只做确定性 diff，不改写文字。把「原始转写正文」和「整理稿」按说话人轮次
对齐后做字级 SequenceMatcher，产出可追溯的修订视图。

〔说明〕与 ⚠ 从修订正文剥离，作为批注，避免把整理者注释当成「新增事实」。
"""
from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import config as C

NOTE_RE = re.compile(r"〔[^〕]*〕")
SPEAKER_SPLIT_RE = re.compile(r"(?=【[^】]{1,20}】)")
SPEAKER_HEAD_RE = re.compile(r"^【([^】]+)】\s*")
SENT_SPLIT = re.compile(rf"(?<=[{C.SENT_ENDINGS}])")
LEADING_TS_RE = re.compile(r"^\s*(?:〔时间\s*)?(\d{1,2}:\d{2}(?::\d{2})?)(?:〕)?\s*")
PUNCT_TRANS = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\uff02": '"',
})
# Word 修订时间戳固定，避免每次重跑 demo 的 .docx 字节都变
REVISION_DATE = "2020-01-01T00:00:00Z"
REVISION_AUTHOR = "整理稿"


@dataclass
class Turn:
    speaker: str | None
    text: str


@dataclass
class AlignedTurn:
    speaker: str | None
    orig: str
    edited_raw: str
    edited_clean: str
    ops: list[tuple[str, str, str]]
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deleted_chars: int = 0
    inserted_chars: int = 0
    orig_speaker: str | None = None
    edited_speaker: str | None = None

    @property
    def changed(self) -> bool:
        return any(tag != "equal" for tag, _, _ in self.ops) or bool(self.notes) or bool(self.warnings)

    def label(self) -> str:
        a, b = self.orig_speaker, self.edited_speaker
        if a and b and a != b:
            return f"【{a}】→【{b}】"
        s = b or a
        return f"【{s}】" if s else "无标签"


def extract_annotations(edited: str) -> tuple[str, list[str], list[str]]:
    """整理稿 → (剥注释后的正文, 〔说明〕列表, 含 ⚠ 的句子)。"""
    notes = NOTE_RE.findall(edited)
    warns = [s.strip() for s in SENT_SPLIT.split(edited) if C.MARK_UNCERTAIN in s and s.strip()]
    clean = NOTE_RE.sub("", edited)
    clean = clean.replace(C.MARK_UNCERTAIN, "")
    clean = re.sub(r"[ \t]+", " ", clean).strip()
    return clean, notes, warns


def split_turns(text: str) -> list[Turn]:
    """按【说话人】切段；没有标签则按空行分段。"""
    text = (text or "").strip()
    if not text:
        return []
    if SPEAKER_HEAD_RE.search(text) or "【" in text:
        parts = [p.strip() for p in SPEAKER_SPLIT_RE.split(text) if p.strip()]
        turns: list[Turn] = []
        for p in parts:
            m = SPEAKER_HEAD_RE.match(p)
            if m:
                turns.append(Turn(m.group(1), p[m.end():].strip()))
            else:
                turns.append(Turn(None, p))
        if turns:
            return turns
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [Turn(None, p) for p in paras] or [Turn(None, text)]


def diff_body(text: str) -> str:
    """只用于字级 diff：剥注释/⚠、统一引号、去掉段首时间戳。展示仍用原文。"""
    t = NOTE_RE.sub("", text or "")
    t = t.replace(C.MARK_UNCERTAIN, "")
    t = t.translate(PUNCT_TRANS)
    t = LEADING_TS_RE.sub("", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def _align_key(t: Turn) -> str:
    body = re.sub(r"\s+", "", diff_body(t.text))[:48]
    return f"{C.canon_speaker(t.speaker) or ''}::{body}"


def align_turns(orig_turns: list[Turn], edit_turns: list[Turn]) -> list[tuple[Turn | None, Turn | None]]:
    """说话人（含【问】/【采访人】别名）一致且段数相同则 1:1；否则按序列对齐。"""
    if len(orig_turns) == len(edit_turns) and all(
        C.canon_speaker(a.speaker) == C.canon_speaker(b.speaker)
        for a, b in zip(orig_turns, edit_turns)
    ):
        return [(a, b) for a, b in zip(orig_turns, edit_turns)]

    a_keys = [_align_key(t) for t in orig_turns]
    b_keys = [_align_key(t) for t in edit_turns]
    sm = SequenceMatcher(a=a_keys, b=b_keys, autojunk=False)
    pairs: list[tuple[Turn | None, Turn | None]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                pairs.append((orig_turns[i1 + k], edit_turns[j1 + k]))
        elif tag == "replace":
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                pairs.append((orig_turns[i1 + k], edit_turns[j1 + k]))
            for k in range(n, i2 - i1):
                pairs.append((orig_turns[i1 + k], None))
            for k in range(n, j2 - j1):
                pairs.append((None, edit_turns[j1 + k]))
        elif tag == "delete":
            for k in range(i1, i2):
                pairs.append((orig_turns[k], None))
        elif tag == "insert":
            for k in range(j1, j2):
                pairs.append((None, edit_turns[k]))
    return pairs


def char_ops(a: str, b: str) -> list[tuple[str, str, str]]:
    sm = SequenceMatcher(a=a, b=b, autojunk=False)
    return [(tag, a[i1:i2], b[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes()]


def _count_ops(ops: list[tuple[str, str, str]]) -> tuple[int, int]:
    deleted = inserted = 0
    for tag, aa, bb in ops:
        if tag == "delete":
            deleted += len(aa)
        elif tag == "insert":
            inserted += len(bb)
        elif tag == "replace":
            deleted += len(aa)
            inserted += len(bb)
    return deleted, inserted


def build_aligned(orig: str, edited: str) -> list[AlignedTurn]:
    pairs = align_turns(split_turns(orig), split_turns(edited))
    out: list[AlignedTurn] = []
    for ot, et in pairs:
        raw = et.text if et else ""
        clean, notes, warns = extract_annotations(raw) if et else ("", [], [])
        src = ot.text if ot else ""
        ops = char_ops(diff_body(src), diff_body(clean))
        d, i = _count_ops(ops)
        orig_sp = ot.speaker if ot else None
        edit_sp = et.speaker if et else None
        out.append(AlignedTurn(
            speaker=edit_sp or orig_sp, orig=src, edited_raw=raw, edited_clean=clean,
            ops=ops, notes=notes, warnings=warns, deleted_chars=d, inserted_chars=i,
            orig_speaker=orig_sp, edited_speaker=edit_sp,
        ))
    return out


def redline_markdown(ops: list[tuple[str, str, str]]) -> str:
    parts: list[str] = []
    for tag, a, b in ops:
        if tag == "equal":
            parts.append(a)
        elif tag == "delete":
            parts.append(f"~~{a}~~" if a else "")
        elif tag == "insert":
            parts.append(f"**{b}**" if b else "")
        elif tag == "replace":
            if a:
                parts.append(f"~~{a}~~")
            if b:
                parts.append(f"**{b}**")
    return "".join(parts)


def redline_html(ops: list[tuple[str, str, str]]) -> str:
    parts: list[str] = []
    for tag, a, b in ops:
        if tag == "equal":
            parts.append(html.escape(a))
        elif tag == "delete":
            parts.append(f"<del>{html.escape(a)}</del>" if a else "")
        elif tag == "insert":
            parts.append(f"<ins>{html.escape(b)}</ins>" if b else "")
        elif tag == "replace":
            if a:
                parts.append(f"<del>{html.escape(a)}</del>")
            if b:
                parts.append(f"<ins>{html.escape(b)}</ins>")
    return "".join(parts).replace("\n", "<br>")


def render_markdown(chunks: list[tuple[str, list[AlignedTurn]]], *, title: str = "") -> str:
    n_turns = sum(len(ts) for _, ts in chunks)
    n_changed = sum(1 for _, ts in chunks for t in ts if t.changed)
    del_n = sum(t.deleted_chars for _, ts in chunks for t in ts)
    ins_n = sum(t.inserted_chars for _, ts in chunks for t in ts)
    out = [
        "# 对照稿（逐段字级修订）",
        "",
        "> 每一说话人轮次先给**修订视图**（删除线 = 原文被删，加粗 = 整理稿新增），再附原始 / 整理全文。",
        "> 浏览器打开同目录 `审阅稿.html` 可按 Word 审阅模式查看；`审阅稿.docx` 可在 Word / WPS 里接受或拒绝修订。",
        "> `〔说明〕` 与 `⚠` 已从修订正文剥离，列在每段批注里，避免把注释当成新增事实。",
        f"> 本篇由字级 diff 实测：{len(chunks)} 块 · {n_turns} 段 · {n_changed} 段有改动 · 删 {del_n} 字 · 增 {ins_n} 字。",
        "",
    ]
    if title:
        out += [f"**项目**：{title}", ""]
    for cid, turns in chunks:
        out += [f"## {cid}", ""]
        for i, t in enumerate(turns, 1):
            label = t.label()
            flag = "有改动" if t.changed else "无改动"
            out += [
                f"### 段 {i} · {label} · {flag}",
                "",
                f"删 {t.deleted_chars} 字 · 增 {t.inserted_chars} 字",
                "",
                "**修订**",
                "",
                redline_markdown(t.ops) or "（空）",
                "",
                "**原始转写**",
                "",
                "> " + (t.orig or "（无）").replace("\n", "\n> "),
                "",
                "**整理稿**",
                "",
                t.edited_raw or "（未整理）",
                "",
            ]
            if t.notes or t.warnings:
                out.append("**批注**")
                out.append("")
                for n in t.notes:
                    out.append(f"- {n}")
                for w in t.warnings:
                    out.append(f"- ⚠ {w}")
                out.append("")
        out += ["---", ""]
    return "\n".join(out)


def render_html(chunks: list[tuple[str, list[AlignedTurn]]], *, title: str = "") -> str:
    n_turns = sum(len(ts) for _, ts in chunks)
    n_changed = sum(1 for _, ts in chunks for t in ts if t.changed)
    del_n = sum(t.deleted_chars for _, ts in chunks for t in ts)
    ins_n = sum(t.inserted_chars for _, ts in chunks for t in ts)
    body: list[str] = []
    for cid, turns in chunks:
        body.append(f'<section class="chunk"><h2 id="{html.escape(cid)}">{html.escape(cid)}</h2>')
        for i, t in enumerate(turns, 1):
            label = t.label()
            cls = "turn changed" if t.changed else "turn unchanged"
            comments = ""
            if t.notes or t.warnings:
                items = "".join(f"<li>{html.escape(n)}</li>" for n in t.notes)
                items += "".join(f"<li class='warn'>{html.escape(w)}</li>" for w in t.warnings)
                comments = f'<aside class="balloon"><div class="balloon-h">批注</div><ul>{items}</ul></aside>'
            body.append(
                f'<article class="{cls}" data-changed="{str(t.changed).lower()}">'
                f'<header><span class="spk">{html.escape(label)}</span>'
                f'<span class="meta">段 {i} · 删 {t.deleted_chars} · 增 {t.inserted_chars}</span></header>'
                f'<div class="row">'
                f'<div class="pane">'
                f'<div class="view review">{redline_html(t.ops) or "（空）"}</div>'
                f'<div class="view original">{html.escape(t.orig or "（无）").replace(chr(10), "<br>")}</div>'
                f'<div class="view edited">{html.escape(t.edited_raw or "（未整理）").replace(chr(10), "<br>")}</div>'
                f'</div>{comments}</div></article>'
            )
        body.append("</section>")

    nav = "".join(f'<a href="#{html.escape(cid)}">{html.escape(cid)}</a>' for cid, _ in chunks)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>审阅稿 · {html.escape(title or "对照")}</title>
<style>
:root {{
  --paper: #f7f4ee;
  --ink: #1c1917;
  --muted: #78716c;
  --line: #e7e0d6;
  --del-bg: #fde8e8;
  --del: #9f1239;
  --ins-bg: #e3f5ea;
  --ins: #146c2e;
  --note: #fff7d6;
  --note-edge: #e8d48b;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.75 "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC",
        "Georgia", "Times New Roman", serif;
}}
.bar {{
  position: sticky; top: 0; z-index: 5;
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
  padding: 10px 20px; background: #fff; border-bottom: 1px solid var(--line);
}}
.bar h1 {{ font-size: 16px; margin: 0; font-weight: 600; }}
.bar .stats {{ color: var(--muted); font-size: 13px; }}
.bar label, .bar button {{
  font: 13px/1.2 system-ui, sans-serif; color: var(--ink);
}}
.bar button {{
  background: #fff; border: 1px solid #d6d3d1; padding: 4px 10px; cursor: pointer;
}}
.bar button[aria-pressed="true"] {{ background: #1c1917; color: #fff; border-color: #1c1917; }}
.legend {{ font: 12px/1.4 system-ui, sans-serif; color: var(--muted); }}
.legend del, .legend ins {{ font-style: normal; padding: 0 3px; }}
main {{ max-width: 980px; margin: 0 auto; padding: 24px 20px 80px; }}
.chunk h2 {{
  font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted); border-bottom: 1px solid var(--line); padding-bottom: 6px;
}}
.toc {{ font: 13px/1.6 system-ui, sans-serif; margin: 0 0 20px; }}
.toc a {{ color: var(--muted); margin-right: 12px; }}
.turn {{
  margin: 18px 0 28px; padding: 0 0 8px;
  border-bottom: 1px dashed var(--line);
}}
.turn header {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px; }}
.spk {{ font: 600 13px/1.2 system-ui, sans-serif; }}
.meta {{ font: 12px/1.2 system-ui, sans-serif; color: var(--muted); }}
.row {{ display: grid; grid-template-columns: 1fr minmax(160px, 28%); gap: 16px; }}
.pane {{ min-width: 0; }}
.view {{ display: none; white-space: pre-wrap; }}
body.mode-review .view.review,
body.mode-original .view.original,
body.mode-edited .view.edited {{ display: block; }}
del {{
  background: var(--del-bg); color: var(--del);
  text-decoration: line-through; text-decoration-thickness: 1.5px;
}}
ins {{
  background: var(--ins-bg); color: var(--ins);
  text-decoration: underline; text-underline-offset: 3px;
  font-style: normal;
}}
.balloon {{
  background: var(--note); border: 1px solid var(--note-edge);
  padding: 8px 10px; font: 13px/1.55 system-ui, sans-serif;
}}
.balloon-h {{ font-weight: 600; margin-bottom: 4px; }}
.balloon ul {{ margin: 0; padding-left: 18px; }}
.balloon .warn {{ color: #9a3412; }}
body.filter-changed .turn.unchanged {{ display: none; }}
@media print {{
  .bar {{ position: static; }}
  .bar button, .bar label {{ display: none; }}
  .row {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 720px) {{
  .row {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body class="mode-review">
<div class="bar">
  <h1>审阅稿{(' · ' + html.escape(title)) if title else ''}</h1>
  <span class="stats">{len(chunks)} 块 · {n_turns} 段 · {n_changed} 段有改动 · 删 {del_n} 字 · 增 {ins_n} 字</span>
  <span>
    <button type="button" data-mode="review" aria-pressed="true">审阅</button>
    <button type="button" data-mode="original" aria-pressed="false">原文</button>
    <button type="button" data-mode="edited" aria-pressed="false">整理</button>
  </span>
  <label for="onlyChanged"><input type="checkbox" id="onlyChanged"> 只看有改动的段</label>
  <span class="legend"><del>删除</del> <ins>新增</ins> · 右侧黄条为批注</span>
</div>
<main>
<nav class="toc">{nav}</nav>
{''.join(body)}
</main>
<script>
const buttons = document.querySelectorAll('[data-mode]');
buttons.forEach(btn => btn.addEventListener('click', () => {{
  document.body.classList.remove('mode-review','mode-original','mode-edited');
  document.body.classList.add('mode-' + btn.dataset.mode);
  buttons.forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
}}));
document.getElementById('onlyChanged').addEventListener('change', e => {{
  document.body.classList.toggle('filter-changed', e.target.checked);
}});
</script>
</body>
</html>
"""


def _xml_safe(text: str) -> str:
    return "".join(ch for ch in text if ord(ch) >= 32 or ch in "\t\n")


def _w_text(tag: str, text: str) -> str:
    if not text:
        return ""
    text = _xml_safe(text)
    space = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f"<{tag}{space}>{xml_escape(text)}</{tag}>"


def _docx_runs(ops: list[tuple[str, str, str]], rev: list[int], author: str, date: str) -> str:
    parts: list[str] = []
    for tag, a, b in ops:
        if tag == "equal" and a:
            parts.append(f"<w:r>{_w_text('w:t', a)}</w:r>")
        elif tag == "delete" and a:
            rid = rev[0]; rev[0] += 1
            parts.append(
                f'<w:del w:id="{rid}" w:author="{xml_escape(author)}" w:date="{date}">'
                f"<w:r><w:delText{_space_attr(a)}>{xml_escape(_xml_safe(a))}</w:delText></w:r></w:del>"
            )
        elif tag == "insert" and b:
            rid = rev[0]; rev[0] += 1
            parts.append(
                f'<w:ins w:id="{rid}" w:author="{xml_escape(author)}" w:date="{date}">'
                f"<w:r>{_w_text('w:t', b)}</w:r></w:ins>"
            )
        elif tag == "replace":
            if a:
                rid = rev[0]; rev[0] += 1
                parts.append(
                    f'<w:del w:id="{rid}" w:author="{xml_escape(author)}" w:date="{date}">'
                    f"<w:r><w:delText{_space_attr(a)}>{xml_escape(_xml_safe(a))}</w:delText></w:r></w:del>"
                )
            if b:
                rid = rev[0]; rev[0] += 1
                parts.append(
                    f'<w:ins w:id="{rid}" w:author="{xml_escape(author)}" w:date="{date}">'
                    f"<w:r>{_w_text('w:t', b)}</w:r></w:ins>"
                )
    return "".join(parts) or "<w:r><w:t></w:t></w:r>"


def _space_attr(text: str) -> str:
    return ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""


def render_docx_bytes(chunks: list[tuple[str, list[AlignedTurn]]], *, title: str = "") -> bytes:
    """生成开启修订的 .docx（stdlib zip + OOXML，不依赖 python-docx）。时间戳固定，字节可复现。"""
    author = REVISION_AUTHOR
    date = REVISION_DATE
    rev = [1]
    paras: list[str] = []

    def p(text: str, style: str = "Normal") -> None:
        paras.append(
            f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
            f"<w:r>{_w_text('w:t', text)}</w:r></w:p>"
        )

    p(f"审阅稿{' · ' + title if title else ''}", "Title")
    p("红色删除线 = 原文被删；下划线插入 = 整理稿新增。在 Word / WPS 中开启「审阅」即可接受或拒绝修订。")
    for cid, turns in chunks:
        p(cid, "Heading1")
        for i, t in enumerate(turns, 1):
            p(f"段 {i} · {t.label()} · 删 {t.deleted_chars} 字 · 增 {t.inserted_chars} 字", "Heading2")
            paras.append(
                f'<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
                f"{_docx_runs(t.ops, rev, author, date)}</w:p>"
            )
            for n in t.notes:
                p(f"批注 {n}")
            for w in t.warnings:
                p(f"待核对 {w}")

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(paras)}<w:sectPr/></w:body></w:document>'
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title">'
        '<w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2">'
        '<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        '</w:styles>'
    )
    settings = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:trackRevisions w:val="true"/>'
        '</w:settings>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/settings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
        '</Relationships>'
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/settings.xml", settings)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
    return buf.getvalue()


def collect_project_chunks(proj: Path) -> list[tuple[str, list[AlignedTurn]]]:
    chunks_dir = proj / C.PROJECT_LAYOUT["chunks"]
    edited_dir = proj / C.PROJECT_LAYOUT["edited"]
    chunk_files = sorted(chunks_dir.glob("chunk_*.md"))
    collected: list[tuple[str, list[AlignedTurn]]] = []
    for cf in chunk_files:
        cid = cf.stem
        orig = C.chunk_body(cf.read_text(encoding="utf-8"))
        ef = edited_dir / f"{cid}.edited.md"
        edited = ef.read_text(encoding="utf-8").strip() if ef.exists() else "（未整理）"
        collected.append((cid, build_aligned(orig, edited)))
    return collected


def write_review_bundle(proj: Path, *, title: str = "") -> dict[str, Path]:
    chunks = collect_project_chunks(proj)
    if not chunks:
        raise FileNotFoundError(f"没有分块：{proj}")
    name = title or proj.name
    review = proj / "review"
    review.mkdir(parents=True, exist_ok=True)
    md_path = proj / C.FILE_COMPARE
    html_path = proj / C.FILE_REVIEW_HTML
    docx_path = proj / C.FILE_REVIEW_DOCX
    md_path.write_text(render_markdown(chunks, title=name), encoding="utf-8")
    html_path.write_text(render_html(chunks, title=name), encoding="utf-8")
    docx_path.write_bytes(render_docx_bytes(chunks, title=name))
    return {"md": md_path, "html": html_path, "docx": docx_path}
