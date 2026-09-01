"""
oral-history-master · 共享配置契约
=================================
所有脚本从这里读取目录结构、标记约定、分块参数，避免硬编码漂移。

设计原则：脚本只做"确定性机械活"（清洗 / 分块 / 一致性校验 / 对照 / 打包）；
真正的"去口语化判断"由主 agent（Editor 角色）按 references/editor.md + examples
逐块完成。脚本绝不替 agent 做语义改写。
"""
from __future__ import annotations

import re
from pathlib import Path

# ── 项目目录结构（每位受访人 / 每次访谈一个 project）────────────────────────
PROJECT_LAYOUT = {
    "sources": "sources",          # 原始转写稿 + ingest 后的归一稿
    "work": "work",                # 中间产物
    "chunks": "work/chunks",       # 分块输入  chunk_001.md ...
    "edited": "work/edited",       # Editor 逐块输出 chunk_001.edited.md ...
    "output": "output",            # 拼接后的整理稿
    "review": "review",            # 交付给"受访人审阅签字"的三件套
}

# project 根下的关键文件
FILE_RAW = "sources/raw.txt"               # 原始转写（ingest 前）
FILE_INGESTED = "sources/ingested.md"      # 清洗 / 说话人分离后
FILE_EDIT_SPEC = "edit_spec.md"            # 整理方针（人读，Surveyor 产出）
FILE_TERM_LOCK = "term_lock.md"            # 执行契约（机读，Editor 每块重读）
FILE_MANIFEST = "work/manifest.json"       # 分块清单 + 进度锚 + 状态
FILE_CLEAN = "output/整理稿.md"             # 拼接成品
FILE_COMPARE = "review/对照稿.md"           # 原始 vs 整理稿 逐段字级修订
FILE_REVIEW_HTML = "review/审阅稿.html"     # Word 式审阅（浏览器）
FILE_REVIEW_DOCX = "review/审阅稿.docx"     # Word/WPS 修订（接受/拒绝）
FILE_FILLER = "review/语气词残留.md"        # 整理稿里疑似未清的 B 类噪音（提示，非改写）
FILE_TODO = "review/待核对清单.md"          # 所有 ⚠ 汇总
FILE_CONSISTENCY = "review/一致性报告.md"   # consistency_checker 产出

# ── 分块参数 ────────────────────────────────────────────────────────────────
CHUNK_TARGET_CHARS = 2400      # 每块目标字数（中文）
CHUNK_MAX_CHARS = 3200         # 硬上限，超过强制切
CHUNK_OVERLAP_SENTS = 2        # 与上一块重叠的句数（给 Editor 上下文）

# 分块文件内的哨兵行（chunker 写、Editor 读、diff/fidelity 据此取"正文"）
CHUNK_OVERLAP_HEAD = "〔上文回顾 · 勿整理，仅供衔接参考〕"
CHUNK_BODY_HEAD = "〔以下为本块正文 · 请整理〕"

# 句子边界（中文）
SENT_ENDINGS = "。！？…"
# 优先切分点：说话人轮次 > 段落 > 句子
SPEAKER_PREFIX_RE = r"^\s*(?:【[^】]+】|（[^）]+）|[A-Za-z一-鿿]{1,6}[:：])"

# ── 标记约定（与 references/shared-standards.md 必须一致）────────────────────
MARK_NOTE_OPEN = "〔"          # 影响意义/可争议改动的行内说明
MARK_NOTE_CLOSE = "〕"
MARK_UNCERTAIN = "⚠"           # 待核对（人名/专名/同音疑似转写错）
MARK_QUESTION = "【问】"        # 采访人的实质提问
# 这些标记在 fidelity_checker / consistency_checker / diff_reporter 中被统计、剥离

# ── 整理方针开关（term_lock 的 switches 段，Editor 据此调尺度）────────────────
DEFAULT_SWITCHES = {
    "genre": "口述史",           # 口述史 / 播客 / 通用访谈
    "fidelity": "中",            # 高 / 中 / 低 仿真度
    "interviewer": "保留",       # 保留 / 脚注 / 删除
    "dialect": "保留",           # 保留 / 标准化+原文括注
    "completion": "最小补全",    # 最小补全 / 仅标注不补
    "fillers": "标准",           # 标准 / 加强（播客默认加强）
}

# 整理稿里疑似残留的 B 类语气词 / 口头禅（filler_scan 提示用，绝不自动删）
FILLER_PHRASES_STANDARD = (
    "就是说", "怎么说呢", "然后呢", "那么个情况", "你知道吧", "你懂我意思吧",
    "对了对了", "那个那个", "就是就是",
)
FILLER_PHRASES_STRONG = FILLER_PHRASES_STANDARD + (
    "反正就是", "然后就是", "所以说", "其实吧", "我觉得吧", "对吧",
    "是吧", "你看啊", "你想啊", "咋说呢", "怎么讲",
)
FILLER_CHARS = ("嗯", "啊", "呃", "额", "唔")
# 「诶/欸」在口述里常是个性口吻（诶你别说），只在加强档当填充提示
FILLER_CHARS_STRONG = FILLER_CHARS + ("欸", "诶")
# 口吃 / 无修辞自我重复：短片段紧挨着再说一遍
STUTTER_RE = re.compile(
    r"([^，。！？\s【】〔〕]{1,12})([，,、]\s*\1){1,}"
)

# 审阅对齐：【问】与【采访人】视为同一轮次
SPEAKER_ALIASES = {
    "问": "采访人", "Q": "采访人", "主持": "采访人", "主持人": "采访人", "主播": "采访人",
    "答": "受访人", "A": "受访人", "嘉宾": "受访人",
}


def canon_speaker(name: str | None) -> str | None:
    if not name:
        return name
    return SPEAKER_ALIASES.get(name, name)


def is_oral_genre(genre: str) -> bool:
    return "口述" in (genre or "口述史")

SKILL_DIR = Path(__file__).resolve().parent.parent


def project_path(projects_root: Path, name: str) -> Path:
    return Path(projects_root) / name


def resolve(name: str, projects_root=None) -> Path:
    """脚本统一入口：name + 可选 projects-root → project 路径。"""
    root = Path(projects_root) if projects_root else (SKILL_DIR / "projects")
    return root / name


def ensure_layout(proj: Path) -> None:
    """创建 project 子目录树（幂等）。"""
    for sub in PROJECT_LAYOUT.values():
        (proj / sub).mkdir(parents=True, exist_ok=True)


def chunk_body(text: str) -> str:
    """从分块文件内容中取出"正文"段（哨兵之后），剥掉上文回顾。"""
    idx = text.find(CHUNK_BODY_HEAD)
    body = text[idx + len(CHUNK_BODY_HEAD):] if idx >= 0 else text
    # 去掉注释行与首尾空白
    lines = [ln for ln in body.splitlines() if not ln.strip().startswith("<!--")]
    return "\n".join(lines).strip()


def parse_switches(path: Path) -> dict:
    """
    解析 term_lock.md 开关表。识别 | 开关 | 取值 | 行。
    键取中文名括号前的英文（如 fidelity（仿真度）→ fidelity），
    或整格（genre / fillers）。缺省回落到 DEFAULT_SWITCHES。
    """
    out = dict(DEFAULT_SWITCHES)
    if not path.exists():
        return out
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not (s.startswith("|") and s.count("|") >= 3):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        raw_key = cells[0]
        val = cells[1]
        if not raw_key or not val or raw_key in ("开关", "取值") or set(raw_key) <= set("-: "):
            continue
        key = re.split(r"[（(]", raw_key, maxsplit=1)[0].strip()
        if key in out or key in DEFAULT_SWITCHES:
            out[key] = val
        elif raw_key in out:
            out[raw_key] = val
    return out


def parse_term_lock(path: Path) -> list[dict]:
    """
    解析 term_lock.md 的术语对照表。
    识别形如 | 规范写法 | 变体/别名 | 类别 | 备注 | 的 markdown 表行。
    返回 [{canonical, variants:[...], kind, note}]，未填充则返回 []。
    """
    if not path.exists():
        return []
    rows: list[dict] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not (s.startswith("|") and s.count("|") >= 4):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2:
            continue
        canonical = cells[0]
        # 跳过表头与分隔行
        if not canonical or canonical in ("规范写法", "规范", "canonical") or set(canonical) <= set("-: "):
            continue
        variants = [v.strip() for v in re.split(r"[;；,，/]", cells[1]) if v.strip()] if len(cells) > 1 else []
        rows.append({
            "canonical": canonical,
            "variants": [v for v in variants if v and v not in ("-", "—", "无")],
            "kind": cells[2] if len(cells) > 2 else "",
            "note": cells[3] if len(cells) > 3 else "",
        })
    return rows


# ── 不确定表述（R4：删除即"伪造确定性"，fidelity_checker 检测）──────────────────
UNCERTAINTY_MARKERS = [
    "大概", "大约", "也许", "可能", "好像", "似乎", "约莫", "差不多", "估计",
    "兴许", "记不清", "记不太清", "记不大清", "印象中", "隐约", "说不准", "说不清",
]

# 副语言标记（A 类特例：保留，不当噪音删）
PARALINGUISTIC_RE = (
    r"[（(【\[]\s*(?:笑|大笑|苦笑|哭|长叹|叹气|停顿|沉默|掌声|拍桌|摇头|点头|"
    r"沉思|哽咽|录音不清|听不清|此处不清|inaudible)[^）)】\]]*[）)】\]]"
)

# ── 数字归一（用于 fidelity 的"新增数字/年份=疑似捏造"检测）────────────────────
_CN_DIGIT = {"〇": "0", "零": "0", "一": "1", "二": "2", "两": "2", "三": "3",
             "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000}
_ARABIC_RE = re.compile(r"\d+")
_CN_NUM_RE = re.compile(r"[〇零一二两三四五六七八九十百千万]{2,}")  # ≥2 字，避开"一个/第一"噪音


def _cn_to_value(seq: str):
    """中文数字串 → 数值字符串；纯数字字符按年份逐位拼（一九五九→1959），否则位值解析。失败 None。"""
    if all(c in _CN_DIGIT for c in seq):
        return "".join(_CN_DIGIT[c] for c in seq)
    total = section = num = 0
    for c in seq:
        if c in _CN_DIGIT:
            num = int(_CN_DIGIT[c])
        elif c in _CN_UNIT:
            u = _CN_UNIT[c]
            if u == 10000:
                total = (total + section + num) * u
                section = num = 0
            else:
                section += (num or 1) * u
                num = 0
        else:
            return None
    val = total + section + num
    return str(val) if val else None


def extract_number_values(text: str) -> set:
    """抽取文本里的数字值（阿拉伯 + 中文数字归一），先剥 〔注〕避免污染。"""
    text = re.sub(r"〔[^〕]*〕", "", text)
    vals = set(_ARABIC_RE.findall(text))
    for m in _CN_NUM_RE.findall(text):
        v = _cn_to_value(m)
        if v:
            vals.add(v)
    return vals
