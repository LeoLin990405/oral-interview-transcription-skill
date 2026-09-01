# 快速上手 · QUICKSTART

> 5 分钟把这套工具跑起来。不熟 Python 也没关系——照着复制命令即可。
> **你的访谈数据全程在自己电脑上，工具不联网、不外传任何内容。**

---

## 0. 准备（一次性）

需要 **Python 3.9 或更高**（macOS / Linux 自带，Windows 去 python.org 装）。检查：

```bash
python3 --version      # 看到 3.9+ 即可
```

把代码拿到本地：

```bash
git clone https://github.com/LeoLin990405/oral-interview-transcription-skill.git
cd oral-interview-transcription-skill
```

> 核心流水线**零第三方依赖**，开箱即用。只有当你的转写稿是 `.docx`/`.xlsx` 时才需要：
> `pip install -r oral-history-master/requirements.txt`

---

## 1. 先看 30 秒 demo（不用跑，直接看文件）

仓库自带一份跑通的**合成样例**（虚构内容），直接打开对比，立刻明白工具在干什么：

| 看这个 | 内容 |
|---|---|
| [`projects/demo/sources/raw.txt`](oral-history-master/projects/demo/sources/raw.txt) | 输入：带"嗯/啊/口误/方言/矛盾"的口语转写 |
| [`projects/demo/output/整理稿.md`](oral-history-master/projects/demo/output/整理稿.md) | 输出：去口语化整理稿 |
| [`projects/demo/review/对照稿.md`](oral-history-master/projects/demo/review/对照稿.md) | 逐段字级修订 + 原始 / 整理全文 |
| [`projects/demo/review/审阅稿.html`](oral-history-master/projects/demo/review/审阅稿.html) | 浏览器里按 Word 审阅模式看红删绿增 |
| [`projects/demo/review/待核对清单.md`](oral-history-master/projects/demo/review/待核对清单.md) | 所有 `⚠` 待核对点（人名/专名） |

---

## 2. 两种用法

### 用法 A · 作为 Claude / Agent Skill（推荐）

这是一套 **Skill**：交给 Claude（或你的 Agent）来编排，它会自动跑脚本 + 做"方针/整理"的判断。

1. 把这两个目录放进你的 skills 目录（如 `~/.claude/skills/`）：
   ```
   oral-history-master/
   oral-history-quality-guard/
   ```
2. 对 Claude 说：**"用 oral-history-master 整理这篇转写稿"**，把转写稿给它。
3. 它会按 7 步流水线走：清洗 → 建项目 → **方针师定方针（文类 / 仿真度 / 语气词力度，这一步会停下来等你确认）** → 分块 → 逐块整理 → 一致性/忠实度校验 → 出复核包（含逐段审阅稿） → 质量门审计 → 按文类提醒签字或发布前核对。

> 关键：流程里有**一个停顿点**——方针师会把"仿真度、开关、术语表、存真红线"打包给你确认，确认后才开整。其余全自动。

### 用法 B · 手动跑脚本

如果你想完全手动控制，脚本是确定性的机械活，你自己在中间做"整理"判断：

```bash
cd oral-history-master/scripts

python3 project_manager.py init   我的访谈                       # 建项目
python3 project_manager.py import 我的访谈 /路径/转写稿.txt --move  # 导入
python3 transcript_ingest.py      我的访谈                       # 清洗+说话人分离
python3 glossary_extractor.py     我的访谈                       # 专名候选预扫

#  ↓ 人工：读 sources/ingested.md，核定 term_lock.md（术语表+仿真度+开关+红线）
#    参照 references/methodology.md 与 templates/term_lock_reference.md

python3 chunker.py                我的访谈                       # 分块

#  ↓ 人工：逐块整理 work/chunks/chunk_NNN.md → work/edited/chunk_NNN.edited.md
#    参照 references/examples.md 的金标准范例（这是改动尺度的基准）

python3 consistency_checker.py    我的访谈                       # 术语一致性
python3 fidelity_checker.py       我的访谈                       # 忠实度门（error 必须返工）
python3 diff_reporter.py          我的访谈                       # 对照稿 + 审阅稿.html/.docx
python3 filler_scan.py            我的访谈                       # 语气词残留提示
python3 package_review.py         我的访谈                       # 拼整理稿 + 待核对清单

python3 project_manager.py status 我的访谈                       # 随时看进度
```

成品在 `projects/我的访谈/output/整理稿.md`，复核材料在 `projects/我的访谈/review/`。

---

## 3. 处理超长访谈（10–20 万字）

一次对话/一个上下文跑不完时，分阶段换窗口续跑，每段都从 `term_lock.md` 重新锚定，保证全篇术语/语气一致。详见 [`workflows/resume-execute.md`](oral-history-master/workflows/resume-execute.md)。

---

## 4. 两道工序，别混

- **Pass 1 · 去口语化**（本工具）→ 整理稿，给受访人审阅签字
- **Pass 2 · 书面化**（发表级编辑）→ 必须在**签字后的整理稿**上另起流程，见 [`workflows/pass2-bookify.md`](oral-history-master/workflows/pass2-bookify.md)

---

## 常见问题

| 问题 | 解决 |
|---|---|
| 转写稿是 Word（.docx） | `pip install python-docx`，import 时直接给 `.docx` 文件 |
| 转写稿是带时间戳的表格（.xlsx） | `pip install openpyxl` |
| 没识别出说话人 | 转写稿里说话人最好写成 `受访人：…` / `采访人：…` / `主持：…` / `嘉宾：…` 或 `问：/答：`；没有也能跑，按段落处理 |
| 想当播客稿用 | 方针师确认时把文类选「播客」、语气词选「加强」；审阅包一样生成，只是不再套用受访人签字句 |
| 一致性报告报"变体未统一" | 说明某专名全篇写法不一致，回 `term_lock.md` 确认规范写法后重跑该步 |
| 忠实度报告报 error | 偏长=可能添了原文没有的内容；偏短=可能删过头。回对应块返工 |

> 遇到任何不顺，把现象发我，一起看。
