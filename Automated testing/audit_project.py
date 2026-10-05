"""Reproducible artifact/provenance audit; does not load models or train."""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent


def trainer_summary(path: Path) -> dict:
    state = json.loads(path.read_text(encoding="utf-8"))
    entries = [x for x in state.get("log_history", []) if "loss" in x]
    losses = [x["loss"] for x in entries]
    return {
        "path": str(path.relative_to(ROOT)),
        "global_step": state.get("global_step"),
        "logged_loss_steps": len(losses),
        "first_loss": losses[0] if losses else None,
        "last_loss": losses[-1] if losses else None,
        "loss_min": min(losses) if losses else None,
        "loss_max": max(losses) if losses else None,
        "loss_non_finite": any(not math.isfinite(x) for x in losses),
        "strictly_monotonic_nonincreasing": all(a >= b for a, b in zip(losses, losses[1:])),
        "eval_loss_entries": sum("eval_loss" in x for x in state.get("log_history", [])),
    }


def main() -> None:
    case_files = sorted((ROOT / "Findings").glob("CaseStudy*.md"))
    trainer_files = sorted(ROOT.glob("outputs_iter_*/checkpoint-*/trainer_state.json"))
    trainer_files += sorted(ROOT.glob("student_model_output/**/trainer_state.json"))
    trainer_records = [trainer_summary(p) for p in trainer_files]
    by_iteration: dict[str, list[dict]] = {}
    for row in trainer_records:
        parent = Path(row["path"]).parts[0]
        by_iteration.setdefault(parent, []).append(row)

    eval_source = (ROOT / "eval_pipeline.py").read_text(encoding="utf-8")
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    finding_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in case_files)
    result = {
        "audit_timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "case_studies_found": [p.name for p in case_files],
        "trainer_state_count": len(trainer_records),
        "trainer_states_by_iteration": by_iteration,
        "empty_iteration_output_directories": [p.name for p in sorted(ROOT.glob("outputs_iter_*")) if p.is_dir() and not any(p.rglob("*"))],
        "outputs_have_training_states_for": sorted({Path(x["path"]).parts[0] for x in trainer_records if Path(x["path"]).parts[0].startswith("outputs_iter_")}),
        "nonempty_evaluation_artifacts": [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".csv", ".txt", ".log"} and ("eval" in p.name.lower() or "perplex" in p.name.lower())],
        "evaluation_implementation": {
            "prompt_masking_present": 'labels[0, :prompt_len] = -100' in eval_source,
            "token_weighted_aggregation_present": "total_loss_sum += outputs.loss.item() * valid_tokens" in eval_source and "avg_loss = total_loss_sum / total_tokens" in eval_source,
            "supports_full_finetune_checkpoint": "full_finetune_path" in eval_source,
            "evaluation_results_saved_to_file": "json.dump" in eval_source or "write_text" in eval_source,
            "evaluation_results_file_present": (ROOT / "evaluation_results.json").exists(),
            "evaluation_output_captures_skipped_count": "skipped" in eval_source.lower(),
            "nan_losses_skipped_but_infinity_not_filtered": "not torch.isnan(outputs.loss)" in eval_source,
        },
        "entropy_implementation": {
            "current_eval_uses_log2_bits": "torch.log2(probs" in eval_source,
            "main_now_uses_log2_bits": "torch.log2(probs" in main_source,
            "conversion_bits_per_nat": 1 / math.log(2),
        },
        "case10": {
            "trainer_state": next((x for x in trainer_records if "outputs_iter_CS10" in x["path"]), None),
            "full_finetune_weight_file_exists": (ROOT / "outputs_iter_CS10/checkpoint-15/model.safetensors").exists() and (ROOT / "student_full_ft_CS10/model.safetensors").exists(),
            "case_report_contains_nan_claim": "NaN" in next((p.read_text(encoding="utf-8", errors="replace") for p in case_files if p.name == "CaseStudy10.md"), ""),
            "case_report_contains_finite_very_large_perplexity": "320495585774" in next((p.read_text(encoding="utf-8", errors="replace") for p in case_files if p.name == "CaseStudy10.md"), ""),
        },
        "baseline_sizes": {
            "algebra_examples": 3,
            "empathy_examples": 2,
            "source": "eval_pipeline.py hard-coded baseline_algebra and baseline_empathy arrays",
        },
        "dataset_provenance": {
            "master_log_entry_count": (ROOT / "Findings/Data_Log_Master.md").read_text(encoding="utf-8", errors="replace").count("## Case Study"),
            "master_log_describes_aggregate_external_datasets": "Aggregate Mega-Batch" in (ROOT / "Findings/Data_Log_Master.md").read_text(encoding="utf-8", errors="replace"),
            "raw_dataset_files_found": [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in {".jsonl", ".parquet", ".arrow", ".csv"}],
        },
        "case_reports_claim_true_executed_perplexities": finding_text.count("True Algebra Perplexity"),
    }
    (OUT / "latest_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
