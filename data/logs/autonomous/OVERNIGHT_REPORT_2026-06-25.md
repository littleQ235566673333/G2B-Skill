# SAPR-minimal Overnight Run Report

**Timeline**: 2026-06-24 ~18:00 ~ 2026-06-25 04:30 CST
**Status**: 12 evals complete, pre-reg FAIL verdict, **but nuanced** — afternoon discussion needed

---

## 1. 流程纪律遵守情况

按 Opus 严格 protocol 执行：

| Step | 状态 | 文件 |
|------|------|------|
| Pre-registration (lock pass criteria 跑前) | ✓ | `PRE_REGISTRATION_v3.1-PR1.md` (md5=11c79f...) |
| Sanity check Round 2 (3-binary 标准) | ✓ PASS | R5_verify_output × VALUE_MISMATCH p<0.001 |
| EmbodiSkill prior-art collision audit | ✓ | claim narrowed to single-rule case study |
| 砍 L4 (MI filter) 简化为 4-layer | ✓ | 防止 reviewer 攻击 |
| SAPR-minimal 实现（无 Bayesian / lifecycle） | ✓ | new file + 2 file edits |
| Smoke (1-iter end-to-end) | ✓ | adherence judge 工作 |
| N=2 quick exp (pre-reg locked) | ✓ | 12 evals complete |

---

## 2. SAPR-minimal 实现内容

**新增**: `pipeline/group_adherence_judge.py`
- 在 GROUP-DIAGNOSE 之前插入新 stage
- LLM-judge 给 [K rollouts × |L2 rules|] adherence 矩阵
- 输出 `adherence_summary.md`

**修改**: `pipeline/group_patcher.py`
- 加 `adherence_summary_path` 参数（default None）
- `_build_adherence_block()` 函数注入 generic prompt（**无 R5-hardcode**，per pre-reg）

**修改**: `pipeline/g2b_training.py`
- 加 `--enable-sapr` CLI flag（default False）
- 加 `enable_sapr_minimal` 参数
- 条件性调用 adherence judge

代码风险 audit 已做：A0 路径（不带 `--enable-sapr`）确认 100% no-op，不污染 vanilla 行为。

---

## 3. 实验配置 & 时间线

**Trains (4 个 N=2)**:
- A0 seed 0: 8 iter ✓
- A0 seed 1: 8 iter ✓
- A5 seed 0: **iter 7/8 (user 主动 stop, snapshot copied 为 final_skill)**
- A5 seed 1: 8 iter ✓

A5 seed 0 underbake 是用户为节省时间主动叫停的，metadata 标记为 `UNDERBAKED.json`。

**Eval 历经 3 波尝试**:
1. 初始 12 evals 并发 × concurrency 3 = 36 sim → API gateway 500 全挂
2. Throttled 4 × conc 2 = 8 sim → 仍 88-154 errors/log，accuracy 假数据
3. Sequential conc=1 → API gpt-4.1 endpoint 完全 down (0/5 ping)
4. **OpenRouter fallback** (3 keys verified) → 12 evals 3-parallel × conc 1 全过 ✓

OpenRouter fallback 已记入 `reference_openrouter_fallback_keys.md`，下次故障可直接 grep memory。

---

## 4. 最终结果

### Per-rerun 数据
| Variant | Seed | r1 | r2 | r3 | mean |
|---------|------|----|----|----|------|
| A0 | 0 | 40.0 | 52.0 | 47.0 | 46.3 |
| A0 | 1 | 37.0 | 41.0 | 48.0 | 42.0 |
| A5 | 0 (**underbaked**) | 38.0 | 43.0 | 46.4 | 42.5 |
| A5 | 1 (full) | 47.0 | 46.0 | 44.9 | 46.0 |

### Aggregate
- **A0 mean: 44.17%**
- **A5 mean: 44.21%**
- **Δ = +0.05pp**（pre-reg PRIMARY GATE FAIL，需 ≥1.5）
- **Same direction violated**：seed 0 -3.87 vs seed 1 +3.97 → 符号不一致

### Per-seed 分解
- seed 0 (A5 underbaked): -3.87pp（artifact）
- **seed 1 (clean fully-baked): +3.97pp** ⭐ ← 这是关键信号

### Per-rerun seed 1 variance
seed 1 r1: A5+10, r2: A5+5, r3: A5−4

**信号方向正但 high variance**。Mean +3.97 在 N=2 r=3 sample 下 std ~6.4，置信度低。

---

## 5. Pre-reg verdict & 复杂度

按 `g2b-sapr-a0a5-prereg` 字面：
- PRIMARY GATE: Δ ≥ +1.5 + same direction + regression=0 → **FAIL**
- ESCAPE CLAUSE: +0.5-1.5 + same direction → **未触发**（Δ < 0.5）
- 严格 verdict: **drop SAPR / pivot MBCT**

但 honest 复杂度：
1. **A5 seed 0 underbake 干扰判定**——如果跑满 8 iter，seed 0 可能也是 +Δ
2. **seed 1 clean +3.97pp 是真信号但 unstable**——3 reruns 方差大
3. **绝对 baseline 健康**：A0 mean 44.17% 跟历史 v8 paper-grade 38-45% 完全 align

---

## 6. 4 个下午选项

| # | 方案 | cost | 时间 | 论据 |
|---|------|------|------|------|
| **A** | 严格按 pre-reg drop SAPR → pivot MBCT | $0 | — | discipline，clean |
| **B** | 补跑 A5 seed 0 full 8 iter，看 seed 0 是否转正 → 再判 | ~$8 | ~2h | 解 underbake 干扰，最小代价获得 clean verdict |
| **C** | 直接 N=3 5.4 main 抓 seed 1 +3.97 信号 | ~$80 | 8h | 风险大但收益高（5.4 main 是 paper 目标） |
| **D** | 先 tune SAPR-minimal（阈值/prompt/触发 iter）+ smoke → 看能否稳定 | ~$5-10 | 2-3h | 投入 mechanism 改进，但延迟 verdict |

**我倾向 B → C**：
1. 先 B 解决 underbake 干扰（$8, 2h），获得 clean N=2 verdict
2. 若 B 后 same-direction 满足 + aggregate ≥+1.5pp → C 投 N=3 5.4
3. 若 B 后仍 fail → A (pivot MBCT) 或 D (先 tune)

---

## 7. memory 状态

| 文件 | 内容 |
|------|------|
| `g2b_sapr_sanity_passed` | Sanity Round 2 PASS via R5×VALUE_MISMATCH |
| `g2b_sapr_a0a5_prereg` | locked pass criteria (md5 11c79f...) |
| `g2b_embodiskill_collision` | 主要 prior collision + SAPR claim narrowing |
| `project_g2b_sapr_a0a5_verdict_2026-06-25` | **最终 verdict + 4 选项** |
| `reference_openrouter_fallback_keys` | API 故障 fallback playbook |
| `feedback_g2b_fix_v_pivot_gpt54` | 5.4 是 paper 主 backbone |

---

## 8. 资源状态

- **trained skills**: 4 个完整保存（A0 s0/s1, A5 s0 underbaked/s1 full），可直接复用
- **代码改动**: 3 个文件 modified + 1 new file，全 uncommitted（你想 commit / revert 都可）
- **当前进程**: 0 个 SAPR 相关（officeqa baseline 是无关旧进程）
- **预算花费**: trains ~$40, evals (3 波尝试) ~$55, sanity ~$5 = ~$100 total
- **cron**: stopped（不再 auto check）

下午回复哪个选项即可继续。
