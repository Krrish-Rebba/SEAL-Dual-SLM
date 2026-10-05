# Case Study 5: High-Volume Fact Flooding (History & Geography)

## Objective
To induce catastrophic forgetting by completely overwhelming the model's 135M parameter capacity. We hypothesize that forcing the model to memorize raw, unstructured, non-logical facts (dates, names, coordinates, atomic weights) will finally force it to overwrite the parameter space previously allocated to mathematical logic (Algebra).

## Methodology
- **Previous Adapter:** Loaded `student_lora_continuous` (pre-trained on Algebra + Calculus + Linguistics).
- **New Training Domain:** High-Volume Facts (American Civil War dates, South American capitals, Ming Dynasty timeline, Roman Emperors, Periodic Table).
- **Teacher:** `HuggingFaceTB/SmolLM2-360M-Instruct`
- **Student:** `HuggingFaceTB/SmolLM2-135M`
- **Utility Threshold:** `30.0`

## Results

> [!WARNING]
> **SUPERSEDED EVALUATION LOGIC**
> The initial perplexity scores in the "Results" section below were generated using a deprecated, lightweight evaluator (using nats instead of bits, and lacking prompt masking). They have been **SUPERSEDED** by the "Empirical Audit Update & Re-Evaluation" section at the bottom of this document, which contains the true, mathematically verified execution scores. Do not use the original numbers for direct comparison.

: Governance Layer
| Input Prompt | HES Score | Status |
| :--- | :--- | :--- |
| "Who were all the wives of Henry VIII..." | 82.64 | PASS |
| "Provide a chronological timeline of the Ming Dynasty." | 82.55 | PASS |
| "Name every capital city in South America..." | 64.24 | PASS |
| "List the absolute exact dates... American Civil War." | 60.76 | PASS |
| "What are the major exports of the top 10 GDP countries?" | 59.60 | PASS |
| "Recite the exact order of Roman Emperors..." | 45.43 | PASS |
| "List the atomic numbers and weights for the first 20 elements..." | 41.91 | PASS |

## Results

> [!WARNING]
> **SUPERSEDED EVALUATION LOGIC**
> The initial perplexity scores in the "Results" section below were generated using a deprecated, lightweight evaluator (using nats instead of bits, and lacking prompt masking). They have been **SUPERSEDED** by the "Empirical Audit Update & Re-Evaluation" section at the bottom of this document, which contains the true, mathematically verified execution scores. Do not use the original numbers for direct comparison.

: Forgetting Measure (FM)
- **Baseline Algebra Perplexity (CS2):** `67.45`
- **Post-Calculus (CS3):** `60.07`
- **Post-Linguistics (CS4):** `54.84`
- **Post-Fact Flooding (CS5):** `49.29`

**Forgetting Measure (FM from Baseline):** `-18.16` 

## Conclusion & Discovery
The model **refuses to break**. In an incredibly surprising turn of events, flooding the model with pure historical and geographical facts *further decreased* its Algebra perplexity to an all-time low of **49.29**.

**Hypothesis on Why This is Happening:**
1. **General Linguistic Coherence:** The model might simply be getting better at predicting *any* coherent English text. By constantly fine-tuning on high-quality teacher responses, the overall loss curve for the model is dropping across the board, masking any domain-specific forgetting.
2. **Latent Knowledge Awakening:** `SmolLM2-135M` already possesses vast pre-trained knowledge. Our LoRA adapter (`r=8`) is likely just learning a "style" or "reasoning format" rather than actually overwriting deep factual weights. As it gets better at "answering questions clearly", its baseline perplexity improves.

To truly induce **Catastrophic Forgetting**, we cannot just train it on *different* facts. We must train it on **Conflicting Logic**.

In **Case Study 6 (Conflicting Logic Training)**, we will force the model to learn abstract, false mathematical axioms (e.g., "1+1=3", "Solving for x means multiplying by zero"). This direct contradiction *must* cause interference in the Algebra weights!

## Execution & Technical Details
- **Total Execution Time:** ~12 minutes
- **Execution & Testing Steps:** Forced the model to generate and train on creative writing and poetry, assuming unstructured data would break the strict logic weights. Re-evaluated Algebra baseline.
- **Model Changes:**
  - **Teacher:** Prompted for creative writing.
  - **Student:** Continuous LoRA update.
- **Result Derivation:** Perplexity dropped to 47.93. Derived that even creative writing in an Instruct-model requires following syntactical rules (e.g., rhymes, stanzas), further feeding the Rule-Following Engine.


## Empirical Audit Update & Re-Evaluation
This case study was natively re-executed under strict mathematically corrected evaluation parameters (bits for entropy, full masking for prompt cross-entropy). The artifacts for this iteration are permanently persisted.
- **True Algebra Perplexity:** `5.6216`
- **True Empathy Perplexity:** `9.5146`




### Dataset Reference (Teacher Knowledge Base)
- **Source:** [HuggingFaceTB/cosmopedia](https://huggingface.co/datasets/HuggingFaceTB/cosmopedia)
- **Content Type:** Synthetic Creative Writing & Textbooks
> [!NOTE]
> For a full breakdown of the raw Teacher Prompts, Student Inputs, and Model Outputs used in this test, refer to the [Master Data Log](file:///C:/Users/Krrish%20Rebba/OneDrive/ドキュメント/RM/Findings/Data_Log_Master.md).
