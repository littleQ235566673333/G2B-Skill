# G2B-Skill (c-topo) 算法框架

> 版本：2026-06-23
> 范围：v8 训练主循环 + 三层 skill 表达 + Patcher 编辑协议
> 代码根：`/Users/unique/auto_research/Project/G2B-Skill`

---

## 0. 设计哲学：把"梯度下降"搬到 skill 文本上

类比标准 ML 训练：

| ML 训练 | c-topo |
|---|---|
| 参数 θ | `SKILL.md` + `references/*.md`（**文本**） |
| 一次 forward | Executor 用当前 skill 跑 K 次 task（**K-rollout**） |
| Loss | K 次跑里成功 / 失败的对比 |
| Gradient | Diagnoser 输出的诊断文本 + tier 标签 |
| Optimizer step | Patcher LLM 调 `write_file` 改 skill |
| Momentum | `momentum_memory.md` 跨 iter 累积的 pattern 记录 |
| Anti-divergence | Anti-wipe guard（>50% 缩水自动回滚） |

核心创新点**不是"让 LLM 改 prompt"**，而是 **结构化的证据流水线** + **分层 skill 表达**。

---

## 1. 主循环（v8）

入口：`pipeline/v8_training.py::run_v8_training()` (L115)，每 iter 走 5 步：

```
EXECUTE → CLASSIFY → DIAGNOSE → MOMENTUM → PATCH → SNAPSHOT
```

每 iter 驱动函数：`_run_iter()` (L207)。

---

## 2. 阶段 1: EXECUTE — K-Rollout 生证据

**为什么 K-rollout 而不是单次执行**：单次只能告诉你"这个 task 对/错"，无法分离"skill 缺陷"和"sampling 噪声"。K 次同 skill 同 task 跑，得到一个 **group**：

```
group = [a₀, a₁, ..., a_{K-1}]   # K=4
```

每个 `a` 是 `Assessment`：`is_correct`、`accuracy.cell_accuracy`、`trajectory_path`（`exec_r{k}.jsonl`）、`cell_comparison`。

代码：`pipeline/group_execution.py::run_group_execute()`

```python
for tid in batch_ids:                                    # batch_size=4
    group = await run_group_execute(K=4, ...)            # 4 rollouts
    per_task_groups.append((tid, group))
# 每 iter 总 rollouts = K × batch_size = 16
```

---

## 3. 阶段 2: CLASSIFY — Group 三态

`v8_training.py::_classify_group()` (L47):

```python
def _classify_group(group):
    n_succ = sum(1 for a in group if a["is_correct"])
    if n_succ == K:  return "all_success"   # 都对
    if n_succ == 0:  return "all_fail"      # 都错
    return "mixed"                          # 部分对部分错
```

这三态是**整个框架的信号源头**：

| 状态 | 信号性质 | 给 patcher 的指导 |
|---|---|---|
| **mixed** | 黄金证据：同 skill 同 task 既能成又能败 → 差异**纯粹由 sampling 决定** → 可定位 skill 没明确写出来的不变量 | `tier=high` 强信号，直接 patch |
| **all_fail** | skill 真盲区 → 但要分 **convergent**（K rollout 都犯同样错=skill 写错了）和 **divergent**（每次错法不一样=skill 没覆盖） | `tier=medium / low` |
| **all_success** | skill 已经掌握 → **不要动**它对应的 section | `tier=protect` |

### v8 vs v7 的关键改进
v7 是"看 primary rollout 的对错"做诊断，丢掉了 group 内的对比信息（trajectory 利用率 ~25%）；v8 改成 group-state 分发，**利用率提到 ~62%**。这是论文里能讲的核心 contribution 之一。

---

## 4. 阶段 3: DIAGNOSE — 三种诊断器分发

入口：`v8_training.py` L249-273

```python
for tid, group in per_task_groups:
    gtype = _classify_group(group)
    if gtype == "mixed":
        diag = run_mixed_group_k_trace_diagnose(group, ...)    # K traces 一次给 LLM
    elif gtype == "all_fail":
        diag = run_all_fail_cluster_diagnose(group, ...)       # K traces，标 convergent/divergent
    else:
        diag = run_diagnose(primary, "contrastive", ...)       # 跨版本对照（vs base skill）
```

### 4a. Mixed 诊断
`pipeline/v8_diagnoser.py::run_mixed_group_k_trace_diagnose()`。
Prompt 让 reviewer 读所有 K 条 trace，**比较成功 rollout 和失败 rollout 的行为差异**，输出："skill 里漏写的不变量是 X，建议在 §Y 加 Z 规则"。这是 c-topo 信噪比最高的信号。

### 4b. All-fail 诊断
`pipeline/v8_diagnoser.py::run_all_fail_cluster_diagnose()`。
读全部 K 条失败 trace，先做**聚类判断**：
- **CONVERGENT**：K 条都犯一样的错 → skill 误导了执行器 → `tier=medium`
- **DIVERGENT**：K 条错法五花八门 → skill 在这类 task 没指导 → `tier=low`

### 4c. All-success 诊断
跨版本 contrastive（vs base trajectories），找"为什么这版能成，base 版不能成"的正向 pattern。但 `tier=protect` —— Patcher 看到这个 tier 不会动对应的 L2 section。

### Evidence Tier 标签
`_assign_evidence_tiers()` (L55) 给每个诊断打 `[Evidence E_X, tier=Y]` 前缀，patcher 据此知道**这条证据有多硬**。这是 c-topo 区别于 v7 SkillGrad 的关键特性 —— **证据加权**。

---

## 5. 阶段 4: MOMENTUM — 跨 iter pattern 累积

**问题**：单 iter 的证据是 4 个 task × K rollouts，太局部。某个 pattern 可能在 iter 3、iter 7、iter 11 都出现，每次都只看当 iter 数据，patcher 会把它当新问题处理 → 重复 patch。

**解法**：`pipeline/momentum.py` 维护跨 iter 状态：

- **`momentum_memory.md`**（持久化）：所有历史 pattern 的 `(trigger, condition, action)` 三元组，每条记 `appeared_in: [iter_3, iter_7, iter_11]`、`remedy_log: [...]`（之前试过的 patch 方法）
- **`momentum_overlay.md`**（当前 iter）：本轮诊断里**每条证据对应到哪个历史 pattern**，外加 routing hint（`add` / `strengthen` / `preserve`）

Patcher prompt 强制 **"按 pattern 而不是按 task patch"**（§3）。多个 task 都触发同一个 pattern 时，patch 一次而不是多次。这避免了"同一处 anchor 被来回改"。

Momentum 还携带 `remedy_log` —— patcher prompt §4.6 规定：**`appeared_in ≥ 3 且 atomic in-place edits 没解决 → 必须考虑结构性 move**（lift to L3 / merge / rewrite）。这是防"无限小修小补"的关键。

---

## 6. 阶段 5: PATCH — 分层编辑

### 6.1 Skill 三层结构（论文核心 contribution）

| 层 | 加载策略 | 内容类型 | 类比 |
|---|---|---|---|
| **L1** YAML frontmatter | 一次性，做 skill selection | `description` ≤ 50 字 | 索引卡 |
| **L2** SKILL.md 正文 | **每次任务都加载** | 通用规则 + 5-15 行 generic 代码 + 决策规则 + L3 指针 | 教科书正文 |
| **L3** `references/*.md` | **指针触发才加载** | 具体操作、edge case、可运行 worked example | 教科书习题册 |

### 6.2 L3 指针的强制形式

```
Read references/<topic>.md when <factual trigger>.
Skip when <near-neighbor>.
```

- **factual trigger** 必须是可观测的事实（如"input 含合并单元格"），不能是抽象判断（"如果你觉得复杂"）
- **near-neighbor** 给出反例，防误触发

### 6.3 Patcher 的硬约束（`prompts/patcher.py` §6 Forbidden actions）

1. **不许 wholesale rewrite**（rewrite from scratch 是历史观察到的 failure mode）
2. **L2 代码里不能含 task-specific value**（不能写 `B26`、`2023-08`，要写 `col_name`、`target_date`）
3. **不许 orphan L3**（建新 L3 必须同 patch 加 L2 指针）
4. **不许 broken pointer**（删 L3 前要先删/改指针）
5. **workflow checklist 不许 append-only**（要 in-place rewrite，否则 unhealthy bloating）
6. **Common Pitfalls 不许 append-only**（同机制 pitfall 必须合并，不能新增 bullet）
7. **verification 必须 prescribe 下一步**（"check X" 不够，要 "if X fails, do Y"）

### 6.4 Anti-wipe Nuclear Guard
`v8_training.py` L322-334：

```python
if post_patch_size < pre_patch_size * 0.5 and pre_patch_size > 1500:
    skill_md_path.write_text(pre_patch_text)   # 回滚
    anti_wipe_triggered = True
```

确定性回滚，**论文 reproducibility 的关键防线**。LLM 偶尔会无视 §6.1 全文重写 → 直接 byte-level 检测并回滚。

---

## 7. 阶段 6: SNAPSHOT & 提前终止

- 每 iter 开头 `_snapshot_skill()` 存 `snapshot_iter_N/` —— 用于事后调试和 forensics
- 早停：连续 4 个 iter `result=all_correct` → break（说明 skill 收敛）

---

## 8. Fix Q / Fix S+T / Fix U 在框架中的位置

**不是新算法**，而是给 patcher 加约束的 ablation：

| 变体 | Patcher 被限制只能改的子系统 |
|---|---|
| **Fix Q** | Query / 问题抽取逻辑 |
| **Fix S+T** | Syntax 解析 + Transform 规则 |
| **Fix U** | User Instruction 解释 + 任务分类 |

主循环、K-rollout、tier 标签、momentum、anti-wipe 全部不变。**这是验证"哪个子系统对最终 acc 影响最大"** 的 controlled experiment。

---

## 9. Seed 体系

三个 seed 控制实验的不同维度，N=3 时只让训练侧变化：

| seed | 控制什么 | N=3 时是否变 |
|---|---|---|
| `master_seed=0` | 100 个 heldout eval task 是哪 100 个 | **固定**（保证可比） |
| `batch_seed` ∈ {0,1,2} | 每 iter 抽哪 4 个进 batch | **变** |
| `training_seed` ∈ {0,1,2} | coreset 选择等内部随机决策 | **变** |

**Bootstrap seed skill** 是另一回事 —— 指起点的手写 `seeds/<bench>/SKILL.md`（如 `seeds/wtq/SKILL.md`），是**文本内容**而非数字。

---

## 10. LLM 角色分工（dbh 网关）

| 角色 | 模型 | 路由 |
|---|---|---|
| **Executor**（跑代码、解任务） | `claude-opus-4-7` | dbh |
| **Reviewer / Diagnoser / Patcher / Momentum**（诊断 + 改 skill） | `gpt-5.5` | dbh |

环境变量：`DISABLE_EXPERIMENTAL_BETAS=1`（dbh→Bedrock 不接受 beta flag）。

入口：`runners/model_dispatch.py`、`runners/model_settings.py`。

---

## 11. Bench 抽象

`bench/__init__.py::get_bench(name)` 统一接口；每个 bench 实现：
- `load_dataset()`
- `prepare_seed_data()`
- `assess_seed()`
- `skill_name`

当前接入：
- **SS** = SpreadsheetBench（核心战场）
- **WTQ** = WikiTableQuestions
- **OQA** = OfficeQA
- SearchQA / LiveMath 的 stub

Eval 时 `master_seed=0` 锁死 100 题，跑 K=1 算 acc。

---

## 12. 信号流总览

```
            ┌──────────────────────────────────────────────┐
            │  K-Rollout (K=4)                             │
            │  group = [a₀, a₁, a₂, a₃]                    │
            └─────────┬────────────────────────────────────┘
                      ▼
            ┌──────────────────────────────────────────────┐
            │  Classify: mixed / all_fail / all_success    │
            └─────────┬────────────────────────────────────┘
                      ▼
            ┌──────────────────────────────────────────────┐
            │  Diagnose (3 prompts) →  [E_X, tier=...]     │
            └─────────┬────────────────────────────────────┘
                      ▼
       ┌──────────────────────────────────────────────────┐
       │  Momentum:                                       │
       │   memory.md (跨 iter pattern + remedy_log)       │
       │   overlay.md (本 iter 路由提示)                  │
       └─────────┬────────────────────────────────────────┘
                 ▼
       ┌──────────────────────────────────────────────────┐
       │  Patcher LLM (按 pattern 编辑 L2/L3)             │
       │   ├─ §4 Writing principles                       │
       │   ├─ §6 Forbidden actions                        │
       │   └─ Anti-wipe guard (确定性 byte check)         │
       └─────────┬────────────────────────────────────────┘
                 ▼
            SKILL.md + references/*.md (下一 iter 输入)
```

---

## 13. 创新点（写 paper 时的卖点）

1. **K-rollout group state** → 把 sampling 噪声从 skill defect 里分离出来；trajectory 利用率 v7 ~25% → v8 ~62%
2. **Evidence tier 化** → mixed / convergent / divergent / protect 四级，patcher 加权使用
3. **L2/L3 分层 + 强制 pointer 形式** → context-efficient，长上下文时 token 利用更高效
4. **Momentum + `remedy_log`** → 防"同一处 anchor 反复小修"的退化
5. **Anti-wipe guard** → 确定性安全网，让 LLM-as-optimizer 的训练**可复现**

---

## 14. 当前已知弱点（badcase 分析方向）

- **L3 reference overhead 在简单 task 上是负担**：12 个 SS-4.1 differential task 里，SkillGrad（flat skill）赢的 task 多是简单公式 / VBA→openpyxl 翻译 —— L3 加载 + pointer 解析的 overhead > 它带来的精度提升
- **`all_success protect` 偶尔过保守**：当一个 section 已经在 4/4 通过，patcher 不动它；但如果新 evidence 提示这个 section **可以更通用**，protect 反而阻碍了 generalization
- **Patcher 对 momentum overlay 的依赖性强**：overlay 写得不准 → patch 跑偏

接下来的 badcase 分析 + 框架改进应着力在这三点。

---

## 15. 关键文件索引

| 模块 | 文件 |
|---|---|
| v8 主循环 | `pipeline/v8_training.py` |
| Group 分类 + tier 标签 | `pipeline/v8_training.py::_classify_group` / `_assign_evidence_tiers` |
| Mixed / All-fail 诊断 | `pipeline/v8_diagnoser.py` |
| All-success contrastive 诊断 | `pipeline/diagnoser.py::run_diagnose` |
| K-rollout 执行 | `pipeline/group_execution.py` |
| Patcher agent | `pipeline/patcher.py` |
| Patcher prompt（L2/L3 规则核心） | `prompts/patcher.py` |
| Momentum agent | `pipeline/momentum.py` |
| Bench 抽象 | `bench/__init__.py` |
| Bootstrap seeds | `seeds/<bench>/SKILL.md` |
| 训练入口 CLI | `scripts/train_v8.py` |

---

## 16. 当前实验状态（截至 2026-06-23）

- **v8+FIX baseline (gpt-4.1, SS, N=3)**：39.3%
- **Fix S+T**：跟 v8+FIX 在 SS-4.1 上无显著差异，差距集中在 12 个 differential task
- **Fix U**：44.3% mean 是 **single training seed × 3 eval reruns** —— **不是 N=3 训练种子**，按 `feedback_no_rush_paper.md` 规则不能写进 paper

### 待办（paper 前必做）
1. 核 Fix U 的 bootstrap seed 来源（确认 `seeds/spreadsheet/SKILL.md` 没泄露 eval 集信息）
2. N=3 真训练：换 `batch_seed × training_seed` 重训 Fix U 各一次（`master_seed=0` 固定）
3. SKILL.md diff（SkillGrad vs Fix S+T）找 c-topo L2 缺失的 dense imperatives
