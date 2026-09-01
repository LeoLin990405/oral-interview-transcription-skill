# 角色：Editor（整理者）

> Editor 是**唯一动文字的角色**——逐块把转写稿去口语化成整理稿。
> 核心纪律：**逐块、串行、主 agent 亲自做、每块重读契约**。

## 🚧 GATE
`term_lock.md` 已由 Surveyor 锁定；`chunker.py` 已生成 `work/chunks/chunk_NNN.md`。

## 必读（进入角色时）
```
references/methodology.md      # 为什么这么改（A/B/C/D + 存真哲学）
references/examples.md         # 改到什么程度（金标准范例 —— 执行尺度看这里）
references/shared-standards.md # 标记约定 + 输入输出契约 + 伦理
```

## 🚨 执行纪律（违反即失败）

1. **逐块整理 term_lock 重读（强制）** — 整理**每一块前**，`read_file <proj>/term_lock.md`。
   所有人名 / 机构 / 专名一律按术语表写，语气按"语气画像"保，开关按 switches 走。
   **不得凭记忆或临场发挥**。这是抗长文上下文压缩漂移的命门。
2. **串行、一块一块** — 顺序整理，不分批群发（禁止"一次 5 块"）。
3. **主 agent 亲自做，禁止丢子 agent** — 整理依赖上下文连续性（前文叙事、受访人语气），
   子 agent 拿不到完整上游语境，会破坏全篇一致性。
4. **范例驱动，不要逐条套规则** — 输出在"改动尺度、用词、标记"上向 `examples.md` 看齐。
5. **存真优先** — 拿不准就不删不改，标 `⚠`。冲突优先级 保护 > 转换 > 清除。
6. **语气词与重复按 fillers 开关清干净** — 标准档也必须清掉无语义「嗯/啊/那个/就是说」、口吃「我是，我是」、无修辞叠说「好多次，好多次」、倾听「对对对」。加强档（播客默认）在同一红线下清得更干净。有功能的「那个项目 / 困难啊 / 对，就是这个意思」留。尺度看 `examples.md` 范例 1、7、8。

## 逐块流程

对 `chunk_001.md` → `chunk_NNN.md`，依次：

1. `read_file <proj>/term_lock.md`（每块都读）。
2. `read_file work/chunks/chunk_NNN.md`。文件结构：
   - `〔上文回顾 · 勿整理，仅供衔接参考〕` 段：**只读不整理**，用来衔接语气和指代。
   - `〔以下为本块正文 · 请整理〕` 段：**这才是要整理的内容**。
3. 按 methodology + examples + term_lock 整理**正文**：
   - B 类噪音静默删（语气词、无修辞重复、假启动、倾听叠词按 fillers 开关）；C 类保守转换；A 类红线保住；D 类按开关。
   - 说话人标签原文是【主持】/【嘉宾】就保持，不要改成【采访人】/【受访人】。
   - 意义级改动加 `〔说明〕`；专名疑点加 `⚠`；采访人实质提问按开关标 `【问】`。
   - 术语严格按 term_lock 术语表归一。
4. 写出 `work/edited/chunk_NNN.edited.md`：**只写整理后的正文**（不带哨兵、不带上文回顾）。
5. 把 manifest 里该块 `status` 置为 `edited`（或运行结束统一更新）。

> 时间线跳跃：本块内不重排；把"建议时间线"记下，全部整理完后汇总到 `output/整理稿.md` 末尾或单独说明。

## 全部整理完 → 自动进入校验与打包
```bash
python3 scripts/consistency_checker.py <name>   # 术语/标签/标记一致性（变体残留→返工）
python3 scripts/fidelity_checker.py   <name>   # 忠实度门：error 必须返工
python3 scripts/diff_reporter.py      <name>   # 对照稿
python3 scripts/package_review.py     <name>   # 整理稿 + 待核对清单
```
- `fidelity_checker` 报 error（偏长疑似添写 / 偏短疑似删过头）→ 回到对应块返工，重跑。
- 全绿后输出完成标记，进入 QA 门（`oral-history-quality-guard`）。

```
## ✅ Editor 阶段完成
- [x] 全部 N 块已整理（每块重读 term_lock）
- [x] consistency_checker 通过（无变体残留）
- [x] fidelity_checker 0 error
- [ ] 下一步：看 review/审阅稿.html（或 审阅稿.docx）逐段核对；QA 门 oral-history-quality-guard 对照原文审忠实度
```
