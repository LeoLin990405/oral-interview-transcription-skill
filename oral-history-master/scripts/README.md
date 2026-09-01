# scripts/ · 确定性流水线工具

> 设计哲学：**脚本只做确定性机械活，语义判断留给主 agent。**
> 「去口语化」这一核心判断由 Editor 角色（主 agent）按 `references/editor.md`
> + `references/examples.md` + `term_lock.md` 逐块完成；脚本绝不替 agent 改写文字。

所有脚本仅依赖 Python 3.9+ 标准库（`.docx/.xlsx` 导入需可选依赖，见 `requirements.txt`）。
统一调用约定：`python3 <script>.py <project_name> [--projects-root DIR]`。

| 脚本 | 作用 | 输入 → 输出 |
|---|---|---|
| `config.py` | 共享契约：目录结构 / 标记约定 / 分块参数 / term_lock 解析 | （被其它脚本 import） |
| `project_manager.py` | 建项目 / 导入转写稿 / 校验 / 进度 | `init` `import` `validate` `status` |
| `transcript_ingest.py` | 清洗 + 说话人分离 + 时间戳归一（不改字） | `sources/raw.*` → `sources/ingested.md` |
| `glossary_extractor.py` | 专名候选预扫 + **变体聚类**（揪出已不一致的同一专名写法） | `ingested.md` → `work/glossary_candidates.json` + `work/term_table_draft.md`（可粘贴进 term_lock） |
| `chunker.py` | 分块（边界切分 + 重叠 + 进度锚） | `ingested.md` → `work/chunks/chunk_NNN.md` |
| `consistency_checker.py` | 跨块术语 / 标签 / 标记一致性校验 | `work/edited/*` + `term_lock.md` → `review/一致性报告.md` |
| `fidelity_checker.py` | 忠实度三信号：①字数比(error 门) ②新增数字/专名(疑捏造) ③不确定删除(伪造确定性) | `chunks/` vs `edited/` + `term_lock.md` → `review/忠实度报告.md` |
| `review_diff.py` | 逐段对齐 + 字级修订（被 diff_reporter 调用） | （库） |
| `diff_reporter.py` | 审阅包：对照稿 + HTML + Word 修订 | `chunks/` + `edited/` → `review/对照稿.md` `审阅稿.html` `审阅稿.docx` |
| `filler_scan.py` | 语气词 / 重复残留提示（不改写） | `edited/` → `review/语气词残留.md` |
| `package_review.py` | 拼接整理稿 + 汇总 ⚠ 待核对清单 | `edited/` → `output/整理稿.md` + `review/待核对清单.md` |
| `report.py` | 质检总览看板（进度+一致性+忠实度+⚠+交付判定） | 各报告 → `review/质检总览.md` |
| `run_pipeline.py` | 编排器：一条命令跑确定性段 | `prep`(ingest→glossary→chunker) / `check`(consistency→fidelity→diff→package→report) |

## 典型一次完整跑（单篇）

```bash
cd oral-history-master/scripts
python3 project_manager.py init  laozhang_interview
python3 project_manager.py import laozhang_interview /path/to/转写稿.txt --move
python3 transcript_ingest.py     laozhang_interview
python3 glossary_extractor.py    laozhang_interview      # → Surveyor 据此填 term_lock
#  〔Surveyor 阶段：主 agent 读 ingested.md，确认整理方针 + 填 edit_spec/term_lock〕
python3 chunker.py               laozhang_interview
#  〔Editor 阶段：主 agent 逐块整理 chunk_NNN.md → work/edited/chunk_NNN.edited.md〕
python3 consistency_checker.py   laozhang_interview
python3 fidelity_checker.py      laozhang_interview      # error → 返工
python3 diff_reporter.py         laozhang_interview
python3 package_review.py        laozhang_interview
#  〔QA 阶段：oral-history-quality-guard 对照原文逐句审忠实度〕
```

20 万字续跑 / 换窗口：见 `workflows/resume-execute.md`。

## 用编排器更省事

```bash
python3 run_pipeline.py prep  我的访谈      # ingest → glossary → chunker（Surveyor/Editor 之前）
#  〔Surveyor 填 term_lock；Editor 逐块整理〕
python3 run_pipeline.py check 我的访谈      # consistency → fidelity → diff → filler_scan → package → report
cat ../projects/我的访谈/review/质检总览.md  # 一页看交付判定
```

## 测试

确定性逻辑有单元测试（零依赖）：

```bash
cd oral-history-master && python3 -m unittest discover tests
```

覆盖：术语解析（含子串跳过）/ 数字归一（一九五九→1959、年份补全容差）/ 分块边界与说话人延续 /
说话人识别与合并 / 忠实度启发式 / 字级审阅 / 语气词扫描 / 文类交付横幅。**改脚本后先跑通测试再提交。**
对 demo 做端到端冒烟：`make smoke`。
