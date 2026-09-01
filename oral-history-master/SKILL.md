---
name: oral-history-master
description: >
  口述史 / 播客 / 通用访谈「整理稿」生成系统（Pass 1 去口语化）。将录音转写稿通过
  「方针师→整理者→质量门」多角色协作，按存真优先原则转换为忠实、可读的整理稿，
  并配套逐段字级审阅包（对照稿 / HTML / Word 修订）。专为长文设计：分块 + 术语锚定 +
  跨块一致性。搭配 companion skill `oral-history-quality-guard` 做交付前忠实度审计。
  触发词：口述史整理、播客转文字、转写稿去口语化、整理访谈记录、口述文本处理、
  oral history、podcast transcript、整理稿、"按口述史要求处理录音转文字"。
  书面化（Pass 2）见 workflows/pass2-bookify.md。
---

# Oral History Master

> 录音转写稿 → 忠实整理稿（Pass 1）。多角色串行流水线 + 确定性脚本 + 机读执行契约。
> **存真 > 可读。** 口述史里录音才是史料；播客同样禁止添写与抹平矛盾。整理稿是最小干预转写。

**核心流水线**：`转写稿 → 归一(Ingest) → 建项目+专名预扫 → ⛔方针师(Surveyor) → 分块 → 整理者(Editor) → 一致性/忠实度门 → 复核包 → 质量门(QA) → 交付(签字)`

> [!CAUTION]
> ## 🚨 全局执行纪律（强制 · 最高优先级）
>
> **本流程是严格串行流水线。违反以下任一条即视为执行失败：**
>
> 1. **串行执行** — 步骤必须按序进行，上一步产物是下一步输入。非 BLOCKING 的相邻步骤在前置满足后可连续推进，无需用户说"继续"。
> 2. **BLOCKING = 硬停** — 标 ⛔ 的步骤必须完全停下，等用户明确回应才继续，**不得替用户做决定**。唯一 BLOCKING 点是 Step 2 方针师的"整理方针确认"。
> 3. **门控进入（🚧 GATE）** — 每步开头列了前置条件，必须先核验再进入。
> 4. **不可越界改写** — 这是口述史。**绝不添加受访人没说的信息**（补全仅限语法成分）；不伪造确定性；不替受访人圆场矛盾；不抹方言与个性。冲突优先级：**A 保护 > C 转换 > D 语境 > B 清除**。
> 5. **逐块 term_lock 重读（强制）** — Editor 整理**每一块前**必须 `read_file <proj>/term_lock.md`，人名/机构/专名按术语表、语气按画像、尺度按 switches。抗长文上下文压缩漂移的命门。
> 6. **逐块串行、主 agent 亲自做** — 顺序一块一块整理，禁止分批（如"一次 5 块"），**禁止把整理丢给子 agent**（破坏跨块语境一致性）。
> 7. **范例驱动，不堆规则** — 整理尺度向 `references/examples.md` 看齐，不要逐条套规则后漂移。
> 8. **禁止假统计** — 不输出"删了 N 个嗯、改了 N 处"。可追溯靠 `review/对照稿.md` / `审阅稿.html` / `审阅稿.docx`（字级 diff），不靠编数字。
> 9. **禁止脚本改写文字** — 脚本只做确定性机械活（清洗/分块/校验/对照/打包）。"去口语化"判断必须由主 agent（Editor）逐块完成，不得写个脚本批量替换了事。
> 10. **质量门必经** — 交付前必须用 companion skill `oral-history-quality-guard` 对照原文逐句审忠实度。未过门不交付。
> 11. **只做 Pass 1** — 本 skill 只做去口语化整理稿。书面化（发表级编辑）是 Pass 2，须在**签字后的整理稿**上另起流程（`workflows/pass2-bookify.md`），**绝不混做**。

> [!IMPORTANT]
> ## 🌐 语言规则
> 回应语言跟随用户与转写稿语言（默认中文）。整理稿、对照稿等产物用受访人原语言。

## 主流水线脚本

| 脚本 | 作用 |
|---|---|
| `${SKILL_DIR}/scripts/project_manager.py` | 建项目 / 导入 / 校验 / 进度（`init`·`import`·`validate`·`status`） |
| `${SKILL_DIR}/scripts/transcript_ingest.py` | 清洗 + 说话人分离 + 时间戳归一（不改字） |
| `${SKILL_DIR}/scripts/glossary_extractor.py` | 专名候选预扫 → Surveyor 据此填 term_lock |
| `${SKILL_DIR}/scripts/chunker.py` | 分块（边界切分 + 重叠 + 进度锚） |
| `${SKILL_DIR}/scripts/consistency_checker.py` | 跨块术语 / 标签 / 标记一致性 |
| `${SKILL_DIR}/scripts/fidelity_checker.py` | 忠实度硬门（添写 / 删过头） |
| `${SKILL_DIR}/scripts/diff_reporter.py` | 逐段字级审阅包（对照稿.md / 审阅稿.html / 审阅稿.docx） |
| `${SKILL_DIR}/scripts/filler_scan.py` | 语气词 / 重复残留提示（不改写） |
| `${SKILL_DIR}/scripts/package_review.py` | 拼接整理稿 + 待核对清单 |

完整文档见 `${SKILL_DIR}/scripts/README.md`。

## 参考与模板索引

| 资源 | 路径 | 何时读 |
|---|---|---|
| 方法论（存真哲学 + A/B/C/D） | `references/methodology.md` | Surveyor 必读 / Editor 选读 |
| 方针师角色 | `references/surveyor.md` | Step 2 |
| 整理者角色 | `references/editor.md` | Step 4 |
| 金标准范例库 | `references/examples.md` | Step 4 必读（执行尺度） |
| 共享标准（标记/契约/伦理） | `references/shared-standards.md` | Editor / QA 必读 |
| 整理方针模板 | `templates/edit_spec_reference.md` | Surveyor 填充 |
| 执行契约模板 | `templates/term_lock_reference.md` | Surveyor 填充，Editor 每块重读 |

## 独立工作流

| 工作流 | 路径 | 用途 |
|---|---|---|
| `resume-execute` | `workflows/resume-execute.md` | 20 万字续跑 / 换窗口（split mode） |
| `pass2-bookify` | `workflows/pass2-bookify.md` | Pass 2 书面化（签字后另起流程） |

---

## 流程

### Step 1：项目初始化 + 转写稿归一
🚧 **GATE**：用户提供了转写稿（txt / md / docx / xlsx 任一）。

```bash
python3 ${SKILL_DIR}/scripts/project_manager.py init <name>
python3 ${SKILL_DIR}/scripts/project_manager.py import <name> <转写稿文件> --move
python3 ${SKILL_DIR}/scripts/transcript_ingest.py <name>      # → sources/ingested.md
python3 ${SKILL_DIR}/scripts/glossary_extractor.py <name>     # → work/glossary_candidates.json
```
**✅ Checkpoint** — ingested.md 生成、专名候选已预扫，进入 Step 2。

### Step 2：方针师阶段（Surveyor · 不可跳过）
🚧 **GATE**：Step 1 完成。

```
Read references/surveyor.md
Read references/methodology.md
```
通读 ingested.md，核定术语表，拟存真红线，写 `edit_spec.md` + `term_lock.md`。

⛔ **BLOCKING**：把整理方针（受访人画像 / 本稿用途 / 仿真度 / 开关 / 术语表 / 存真红线 + 规模提示）打包呈现，**等用户明确确认或修改**。这是唯一核心确认点；确认后所有后续步骤自动推进。

**✅ Checkpoint** — 方针确认、term_lock 锁定，自动进入 Step 3。

### Step 3：分块
🚧 **GATE**：term_lock.md 已锁定。
```bash
python3 ${SKILL_DIR}/scripts/chunker.py <name>     # → work/chunks/chunk_NNN.md + manifest
```
**✅ Checkpoint** — 分块完成，进入 Step 4。

### Step 4：整理者阶段（Editor）
🚧 **GATE**：Step 3 完成。
```
Read references/editor.md
Read references/examples.md          # 执行尺度
Read references/shared-standards.md
```
- **整理每一块前 `read_file <proj>/term_lock.md`**（强制，抗漂移）。
- 逐块、串行、主 agent 亲自做；按 methodology + examples + term_lock 整理**正文**。
- 输出 `work/edited/chunk_NNN.edited.md`（只写整理后正文）。
> ⚠️ 禁止子 agent 整理；禁止分批；禁止写脚本批量替换。

**✅ Checkpoint** — 全部块整理完，进入 Step 5。

### Step 5：一致性 + 忠实度门（强制）
🚧 **GATE**：Step 4 完成。
```bash
python3 ${SKILL_DIR}/scripts/consistency_checker.py <name>   # 变体残留 → 返工
python3 ${SKILL_DIR}/scripts/fidelity_checker.py   <name>   # error → 必须返工
```
- `consistency_checker` 报变体未统一 → 回 Editor 修该块。
- `fidelity_checker` 报 error（偏长疑似添写 / 偏短疑似删过头）→ 回对应块返工，重跑直到 0 error。

**✅ Checkpoint** — 两个门全绿，进入 Step 6。

### Step 6：复核包
🚧 **GATE**：Step 5 全绿。
```bash
python3 ${SKILL_DIR}/scripts/diff_reporter.py  <name>    # → review/对照稿.md + 审阅稿.html/.docx
python3 ${SKILL_DIR}/scripts/filler_scan.py    <name>    # → review/语气词残留.md
python3 ${SKILL_DIR}/scripts/package_review.py <name>    # → output/整理稿.md + review/待核对清单.md
```
**✅ Checkpoint** — 整理稿 + 四份复核报告齐备，进入 Step 7。

### Step 7：质量门 + 交付（QA · 强制）
🚧 **GATE**：Step 6 完成。

用 companion skill **`oral-history-quality-guard`** 完成忠实度审计：
- **对照原文逐段**审 `review/审阅稿.html`（或 `对照稿.md` / `审阅稿.docx`），确认无捏造、无伪造确定性、无圆场矛盾、无抹方言；
- 抽查 ⚠ 是否该标尽标、术语是否全篇统一、`语气词残留.md` 里是否还有该清的噪音；
- 发现问题 → 回 Editor 修对应块，重跑 Step 5–6。

**未过 QA 门不得交付。** 交付时必须明确说明：已逐段审忠实度、已查捏造/确定性/矛盾/方言、已核 ⚠ 与术语一致性。

最终提醒按文类：
- 口述史：此整理稿（Pass 1）须经受访人审阅签字方可使用。
- 播客 / 通用访谈：发布前请主持 / 嘉宾核专名与事实。
⚠ 待核对处请对录音/原始材料核定后回填 term_lock 重跑一致性。书面化（Pass 2）请另起 `workflows/pass2-bookify.md`。

---

## 角色切换协议
切换角色前**必须先读**对应 reference，并输出标记：
```
## [角色切换：<角色名>]
📖 读取角色定义：references/<file>.md
📋 当前任务：<简述>
```

## Notes
- 进度查看：`python3 scripts/project_manager.py status <name>`
- 20 万字：Step 2 后若规模重，按 `workflows/resume-execute.md` 转 split mode（换窗口续跑）。
- 依赖：核心流水线仅需 Python 3.9+ 标准库；`.docx/.xlsx` 转写稿需 `pip install -r requirements.txt`。
