# 2026-06-19 早安总结 — G2B-v8 达成 SkillGrad PARITY

## 核心结果

**v8 multi-seed = 69.0 ± 1.0 hard PASS / 100 ≈ SkillGrad multi-seed 69 ± 2.1**

| version | per-seed | mean | std | cell mean |
|---|---|---|---|---|
| SkillGrad multi-seed | 71, 67, 70 | **69** | ±2.1 | 81.0% |
| **v8 multi-seed** | **68, 70, 69** | **69.0** | **±1.0** | 79.4% |
| v4 multi-seed (prior) | 60, 61, 62 | 61 | ±1.0 | 74.7% |
| v7 (group_evidence only) | 64 single | — | — | 79.7% |

**v8 比 SkillGrad std 更紧（±1.0 vs ±2.1）—— G2B 在稳定性上还有优势**。

## 路径回顾（昨晚的决策链）

1. v4 multi-seed 揭示 G2B 有 -8pp 真实 gap vs SkillGrad （不是 noise）
2. 诊断 root cause：v4 重写了 SkillGrad 4/5 个 prompt（违反 framework doc §1 "additive first"）
3. 设计 v7 = SkillGrad 原 prompt + K=4 group + group_evidence.md 注入到 patcher input
4. v7 single = 64，缩到 -5pp gap
5. 你 push 了关键 insight："轨迹数据不要浪费"
6. 设计 v8 = v7 + group-state-aware diagnose dispatch (mixed K-trace contrastive + all_fail K-trace clustering)
7. v8 multi-seed = 69 = SkillGrad parity ✅

## v8 的核心设计

```
v7: 每 task 4 个 trajectory → 1 个进 diagnoser pipeline (其余进 group_evidence 表)
v8: 每 task 4 个 trajectory → 全部进对应 prompt (mixed K-trace contrastive / all_fail K-trace clustering)
```

Trajectory 利用率从 25% (v7) 升到 62% (v8)，prompt 内容质量大幅提升。

## v8 SKILL.md 关键学到的 high-leverage rules

源自 mixed K-trace contrastive (53117): **"follow sheet examples over prompt"** —— 当 prompt 文字和 sheet 示例冲突时，sheet 示例为准。这是 SkillGrad 那种 execution-mode-level meta rule，v7 单 trace failure diagnoser 写不出来。

源自 all_fail K-trace clustering (263-1): **"never place explanatory text or VBA/source lines into evaluated cells, even when prompt mentions VBA/Power Query"** —— 区分 prompt 框架（"give me a macro"）和 evaluator 实际打分对象（worksheet cells）。

## v7 → v8 task-level diff

- both PASS (单 seed 比较): 57
- v8-only gains: 11 个 (主要是 formula synthesis 类: 33157, 51262, 7902, 43657 等)
- v7-only losses: 7 个 (pattern: "Recreate formulas exactly" 类被 v8 over-strict 规则误伤: 50631, 54638; 复杂 INDEX/MATCH: 55468)
- both fail: 25

## 今晚的钱

| item | cost |
|---|---|
| v4 multi-seed 400-task (过早脚本 bug 跑全集) | $74 |
| SkillGrad multi-seed 100-slice | $25.7 |
| v7 train + eval | $19.2 |
| v8 train | $12.78 |
| v8 eval (3 seeds) | $19.35 |
| smoke + preflight + prompt tests | ~$5 |
| **total today** | **~$156** |

## 早上可以决定的事

### 1. v8.1 prompt iteration 是否要做？

7 个 v8-only losses 主要是 v8 SKILL.md 学的"don't write code in cells"规则在 "Recreate formulas exactly" 任务上 over-fire。诊断 prompt 设计上可以加 scope clause：

```
当 task 明确要求 "create a formula" / "recreate formulas" 时，
"don't write code in cells" 规则不适用 — formula 是合法 cell content。
```

潜在收益: +3-4pp（v8 mean 69 → ~72-73, 有可能 BEAT SkillGrad）  
风险: 可能掉 v8 的 11 wins 中的几个（prompt 改动副作用）  
成本: ~$30 (train + single-seed eval) 或 ~$45 (含 multi-seed)

### 2. 直接进入"增量模块" phase

按你昨晚的"先持平 grad, 后续做增量模块"思路，可以现在开始设计 incremental:
- K=8 (从 K=4 升 K=8 看是否更多 mixed group)
- Plan-level diversity (rollout 间强制不同 plan，而非 temperature 抖动)
- WTQ 上重做 v8（已知 v4 在 WTQ 上和 SkillGrad parity；v8 可能 BEAT）

### 3. 写 paper

v8 = parity 已经是可写的 paper 故事:
- mechanism: K-rollout group-aware diagnose dispatch
- empirical: parity with SkillGrad multi-seed, TIGHTER variance
- ablation: v4 → v7 → v8 progression shows each design choice's contribution

## 状态

- 所有 v8 artifacts 在 `results/runs/g2b-v8_gpt-5.4/`
- code 在 `pipeline/v8_*.py` + `prompts/v8_diagnoser.py` + `scripts/train_v8.py`
- memory 已更新: `[G2B v8 result (PARITY ACHIEVED)]`
- 没有正在跑的进程

醒来跟你聊下一步。
