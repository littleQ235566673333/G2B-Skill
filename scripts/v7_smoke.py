"""v7 smoke test: 1 iter, 4 tasks, K=4 group rollouts.

Minimum viable test that:
1. group_execute K=4 produces K assessments per task
2. v7_helpers.build_group_evidence_md writes a sane file
3. SkillGrad's classify_batch + run_diagnose work on PRIMARY assessments
4. SkillGrad's run_patch reads group_evidence_path and writes new SKILL.md

If this passes, full v7 training (10 iter) is just a loop wrapper.
"""
import asyncio, os, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "true"

from bench import get_bench
from pipeline.diagnoser import assemble_diagnoses, classify_batch, run_diagnose
from pipeline.group_execution import run_group_execute
from pipeline.patcher import run_patch
from pipeline.v7_helpers import build_group_evidence_md, pick_primary_assessment
from runners.cost_tracker import CostTracker
from runners.model_dispatch import get_client_for_model
from runners.soffice import install_soffice_wrapper

BATCH_IDS = ["50088", "160-6", "142-19", "57033"]
K = 4
MODEL = "gpt-5.4"


async def main_async():
    project_root = Path(".").resolve()
    workdir = Path("results/runs/g2b-skill-spreadsheet_gpt-5.4_v7_smoke")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    iter_dir = workdir / "iter_1"
    iter_dir.mkdir()

    # Stage seed skill into workdir/skills/xlsx (mutated in-place by patcher)
    skills_dir = workdir / "skills"
    seed_src = Path("seeds/xlsx")
    skill_dest = skills_dir / "xlsx"
    skill_dest.mkdir(parents=True)
    shutil.copy2(seed_src / "SKILL.md", skill_dest / "SKILL.md")
    if (seed_src / "references").exists():
        shutil.copytree(seed_src / "references", skill_dest / "references")
    seed_skill_size = (skill_dest / "SKILL.md").stat().st_size
    print(f"Seeded skill: {skill_dest}/SKILL.md ({seed_skill_size} bytes)")

    install_soffice_wrapper(workdir, Path("/tmp/skillgrad_soffice.lock"))
    bench = get_bench("spreadsheet", data_dir="results/normalized")
    dataset = bench.load_dataset()
    id2idx = {str(s["id"]): i for i, s in enumerate(dataset)}

    cost = CostTracker(MODEL)
    sem = asyncio.Semaphore(8)
    client = get_client_for_model(MODEL)

    # ── EXECUTE: K=4 rollouts per task ──
    print(f"\n── EXECUTE (K={K} × {len(BATCH_IDS)} tasks = {K*len(BATCH_IDS)} rollouts) ──")
    per_task_groups = []
    primaries = []
    for tid in BATCH_IDS:
        idx = id2idx[tid]
        task_workdir = iter_dir / f"task_{tid}"
        task_workdir.mkdir(parents=True)
        group_assessments = await run_group_execute(
            bench=bench, dataset=dataset, idx=idx, K=K,
            workdir=task_workdir, semaphore=sem, skills_dir=skills_dir,
            model=MODEL, project_root=project_root, max_turns=25,
            cost_tracker=cost, openai_client=client,
        )
        per_task_groups.append((tid, group_assessments))
        primary = pick_primary_assessment(group_assessments)
        primaries.append(primary)
        n_succ = sum(1 for a in group_assessments if a["is_correct"])
        print(f"  {tid}: K={K}, n_succ={n_succ}, primary rollout=r{primary.get('_rollout_idx')} ({'PASS' if primary['is_correct'] else 'FAIL'})")

    # ── BUILD group_evidence.md ──
    group_evidence_path = build_group_evidence_md(per_task_groups, iter_num=1, iter_dir=iter_dir)
    print(f"\nWrote group evidence: {group_evidence_path} ({group_evidence_path.stat().st_size} bytes)")

    # ── CLASSIFY (on primaries) ──
    failed, contrastive = classify_batch(primaries)
    print(f"\n── CLASSIFY (primaries): {len(failed)} failed, {len(contrastive)} contrastive ──")

    # ── DIAGNOSE ──
    print(f"\n── DIAGNOSE ──")
    base_traj_dir = Path("results/base_trajectories/master_0_heldout_42/spreadsheet/gpt-5.4")
    diag_tasks = []
    for a in failed:
        diag_tasks.append(run_diagnose(a, "failure", iter_dir, skills_dir, base_traj_dir,
                                       MODEL, project_root, sem, cost, skill_name="xlsx"))
    for a in contrastive:
        diag_tasks.append(run_diagnose(a, "contrastive", iter_dir, skills_dir, base_traj_dir,
                                       MODEL, project_root, sem, cost, skill_name="xlsx"))
    diagnoses = await asyncio.gather(*diag_tasks)
    batch_diagnoses_path = iter_dir / "batch_diagnoses.md"
    assemble_diagnoses(diagnoses, primaries, batch_diagnoses_path)
    print(f"Wrote diagnoses: {batch_diagnoses_path} ({batch_diagnoses_path.stat().st_size} bytes)")

    # ── PATCH (with group_evidence injection — v7 additive) ──
    print(f"\n── PATCH (v7: group_evidence_path injected) ──")
    patch_output = await run_patch(
        batch_diagnoses_path, skills_dir, MODEL, project_root, cost, iter_dir,
        overlay_path=None, momentum_memory_path=None,
        group_evidence_path=group_evidence_path,
    )

    # ── verify SKILL.md changed ──
    new_skill_size = (skill_dest / "SKILL.md").stat().st_size
    print(f"\n── verify ──")
    print(f"  SKILL.md before: {seed_skill_size} bytes")
    print(f"  SKILL.md after:  {new_skill_size} bytes (Δ {new_skill_size - seed_skill_size:+d})")
    print(f"  patch output (first 200 chars): {patch_output[:200]}")
    print(f"\nCost: ${cost.total_cost:.3f}")
    print(f"Workdir: {workdir}")


if __name__ == "__main__":
    asyncio.run(main_async())
