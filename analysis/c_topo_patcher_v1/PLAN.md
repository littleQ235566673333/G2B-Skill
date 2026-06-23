# Group Patcher v9 改造方案（最终版，开工用）

日期：2026-06-21
死线：2026-07-04 paper

## 1. 设计总纲：4-cell × 2-axis

把 group state × evidence kind 拆成二维：

| state \ kind          | process            | function                                         |
| --------------------- | ------------------ | ------------------------------------------------ |
| all_success (HARD)    | (defer, future work) | (defer, future work)                              |
| all_success (EASY)    | 不动               | 不动                                             |
| mixed                 | v8 主路径，保留    | **新：sub-rule，由 evidence_kind 标签触发**       |
| all_fail CONVERGENT   | (不写 process)     | **新：negative function rule, cross-task 印证**   |
| all_fail DIVERGENT    | force_pending      | force_pending                                     |

本轮只做两个加粗 cell。其余写进 limitation。

## 2. 三处代码改动

### 改动 A — `pipeline/group_diagnoser.py` prompt

- mixed group：要求 diagnoser 输出 `evidence_kind: process | function | both`
- all_fail CONVERGENT：取消 `_validate_card` 中"all_fail → 强制 evidence_strength=low"的硬置（group_diagnoser.py:220-227）

### 改动 B — `pipeline/group_patcher.py::deterministic_prefilter`

新增字段 `cross_task_convergent`：从 momentum_memory pattern_blocks 中筛出
- group_type == "all_fail"
- pattern_kind == "CONVERGENT"
- distinct task_ids in source_groups ≥ 2
- contradiction_count == 0

不动现有 force_pending / discard_candidates / inspectable 语义（向后兼容）。

### 改动 C — `prompts/group_patcher.py`

§3a 路由表新增独立分支（不是新 route，是 core 的子形态）：

> **若 pid ∈ cross_task_convergent**：route = core，但写为 **negative function rule** 形态——
> - 仅允许 "avoid X" / "do not Y" 句式（negative-only）
> - 用 `<!-- F: avoid -->` HTML 注释锚定到对应 process H3 后
> - 不新建 L2 H2，不许写 positive prescription
> - mixed evidence_kind=function 也走同一形态（attached to process H3）

§7 加 §7c worked example：一个 all_fail CONVERGENT 跨 2 task → function rule 的样例。

## 3. 三道安全闸（Q3 约束）

CONVERGENT 跨任务印证不能放水。硬约束：

1. ≥ 2 distinct task_ids（在 source_groups 上结构化判，非语义匹配）
2. negative-only 句式（拒绝 positive prescription）
3. contradiction_count == 0（任何反例立即退回 pending）

任何一条不满足 → 走原 force_pending 路径。

## 4. 验证计划

- multi-seed N=10（按 [protocol_v2_multiseed.md](../c_topo_ablation/protocol_v2_multiseed.md)）
- A/B：v8 baseline vs v9（A+B+C 三处改动作为整体）
- 不做单独 ablation（预算不够；改动 A/B/C 是耦合的，单独拆没意义）
- bench：OQA-5.4 + SS held-out（mixed evidence_kind 主要在 SS 起作用）

## 5. 不做的事（明确止损）

- ❌ 不再迭代 SCHEMA.md
- ❌ 不再 calibrate Jaccard（cross-task 用 task_id 结构化匹配，不用 token-Jaccard）
- ❌ 不再开 Opus 讨论轮
- ❌ 不做 all_success in HARD（信号 <2%）
- ❌ 不做 K=8 DIVERGENT 实验（预算）

## 6. Limitation 段落（paper 用）

> Two extensions were considered but not pursued: (a) extracting positive
> function rules from all_success groups in difficult task categories,
> deferred due to signal sparsity (<2% of groups in fix runs); (b) larger
> K-rollouts to decompose DIVERGENT all_fail into multiple CONVERGENT
> sub-patterns, deferred due to inference budget.
