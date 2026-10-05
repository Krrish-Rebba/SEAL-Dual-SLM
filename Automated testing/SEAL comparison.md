# SEAL Paper and Dual-SLM Project: Final Comparison

**Checked:** 2026-10-04  
**Primary sources:** [NeurIPS 2025 paper](https://papers.neurips.cc/paper_files/paper/2025/file/6b41e04c41726e2a60e456d0a2b961ab-Paper-Conference.pdf), [arXiv record](https://arxiv.org/abs/2506.10943), [MIT CSAIL summary](https://www.csail.mit.edu/news/teaching-large-language-models-how-absorb-new-knowledge).

## What the SEAL paper actually establishes

SEAL is an RL-trained policy for producing self-edits: generated training material and, optionally, update directives. Each proposed edit is applied, evaluated on its downstream task, and rewarded according to whether it improves that task. The paper demonstrates knowledge incorporation and few-shot adaptation. In its continual-learning experiment, it sequentially incorporated passages and re-evaluated prior tasks after each update. Earlier-task performance gradually declined. The authors explicitly state that this setup did not optimize retention, that forgetting was incomplete rather than total collapse, and that retention mechanisms are future work.

The paper also explicitly says its implementation uses one model for generating and learning from self-edits, **but names a teacher–student formulation as a possible decoupling**. It suggests the student could learn from separate-teacher edits and the teacher could be RL-trained to maximize student improvement. Thus a dual-model idea is not inherently opposed to SEAL; it is a plausible architecture extension suggested by the paper itself.

## How this project relates

This project has a frozen SmolLM2-360M-Instruct teacher and a 135M student updated sequentially through one persistent LoRA adapter. That decouples generation from adaptation and prevents training updates from changing the teacher or the student's frozen base weights. This can protect the original base model and keep the teacher's generation distribution stable.

But it does not yet demonstrate that the *adapted system* avoids forgetting. The adapter itself is continuously updated and can overwrite earlier adapter knowledge. If turned off, the frozen base may recover its original behavior, but the newly learned content disappears too. The entropy gate is a heuristic for predictive uncertainty; it neither checks truth nor directly penalizes regressions on previously learned tasks. The project does not have SEAL's learned/RL-optimized self-edit policy and downstream reward loop, so the accurate description is a **teacher–student continual fine-tuning pipeline inspired by self-adaptation**, rather than a reproduction or direct comparison of SEAL.

## Is it “up to the mark” for the stated research aim?

**As an architecture proposal:** promising and directionally relevant. The frozen teacher plus student adapter is a reasonable decoupled design, and a frozen base gives a concrete parameter-preservation property.

**As evidence that it overcomes catastrophic forgetting:** not yet. Saved training checkpoints verify training runs, not retention. The listed perplexities lack a consistently preserved, fully auditable evaluation record. Baselines in the current code are only 3 algebra examples and 2 empathy examples. The cases use different training topics and settings, while no controlled comparison runs the SEAL-style single-model update and the dual-SLM system on the same stream, seed, base model, data, and evaluation suite. A stable loss on new training data cannot establish old-task retention.

The defensible claim is: **“A frozen-teacher, frozen-base-plus-LoRA design may reduce interference with the pretrained base and is a candidate mitigation for the forgetting observed in SEAL’s tested sequential-edit setup.”** The stronger claim that it has overcome catastrophic forgetting requires a controlled experiment.

## Minimum experiment to substantiate the claim

1. Use a fixed, versioned sequence of tasks/passages with disjoint training and held-out evaluation examples. Save exact prompts, teacher outputs, HES values, random seeds, model revisions, adapter hashes, and hardware details.
2. Measure each task before adaptation and after every update. Use task-appropriate accuracy/exact-match or blinded correctness scoring, with answer-only token-weighted cross-entropy as a secondary metric. Report the number of examples and confidence intervals.
3. Compare under the same base model, training examples, token/update budget, and seeds: (a) sequential full/model update baseline, (b) sequential persistent LoRA, and (c) the proposed fixed-teacher + HES + student-LoRA pipeline. Include no-update and replay or per-task adapters as controls.
4. Report both plasticity on the new task and retention on all prior tasks; include average forgetting (per task, pre-update/best prior score minus final score), final average performance, and variance across multiple seeds. Define in advance what non-inferiority margin counts as “no material forgetting.”
5. Preserve evaluation results and skipped/non-finite counts to `evaluation_results.json` (or a CSV/JSONL ledger) after each update. The current evaluator writes a JSON summary when it runs, but the file is not currently present; it also skips NaN-loss examples without recording a skipped count, which can make a reported finite perplexity misleading.

Until this is run, avoid “SEAL inevitably collapses,” “total representational collapse,” and “catastrophic forgetting solved.” The paper's claim is narrower: degradation appeared in its chosen sequential-edit experiment without a retention objective.
