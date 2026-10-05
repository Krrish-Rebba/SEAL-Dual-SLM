import os

cs_details = {
    "CaseStudy1.md": """
## Execution & Technical Details
- **Total Execution Time:** ~4 minutes
- **Execution & Testing Steps:** The Teacher model generated 5 standard responses. Logits were captured, HES was calculated, and the top-tier data was passed to the Student. The Student underwent a 10-step LoRA fine-tuning process.
- **Model Changes:** 
  - **Teacher:** `SmolLM2-360M-Instruct` (Frozen, 4-bit)
  - **Student:** `SmolLM2-135M` (Base, initialized with new LoRA r=8 adapter)
- **Result Derivation:** Results were derived by tracking the SFTTrainer training loss, verifying that the 135M model could successfully minimize loss on 360M-generated syntax within 4GB VRAM.
""",
    "CaseStudy2.md": """
## Execution & Technical Details
- **Total Execution Time:** ~6 minutes
- **Execution & Testing Steps:** Executed the continuous learning pipeline. Evaluated the model against a static Algebra validation dataset to establish a pre-training baseline.
- **Model Changes:**
  - **Teacher:** No structural changes.
  - **Student:** Continued training on the saved `./student_lora_continuous` adapter.
- **Result Derivation:** The Perplexity score (67.45) was mathematically derived by passing the Algebra baseline dataset through the Student model, calculating the Cross-Entropy loss of the predicted tokens against the ground truth, and taking the exponential (`math.exp(avg_loss)`).
""",
    "CaseStudy3.md": """
## Execution & Technical Details
- **Total Execution Time:** ~10 minutes
- **Execution & Testing Steps:** Prompted the Teacher with non-English (French/German) queries. Filtered the data through the Governance plane and trained the Student. Immediately re-evaluated the Student on the exact same Algebra baseline to test for catastrophic forgetting.
- **Model Changes:**
  - **Teacher:** Forced to generate multi-lingual content.
  - **Student:** Continuous LoRA update on the linguistic dataset.
- **Result Derivation:** By comparing the pre-linguistic Algebra perplexity against the post-linguistic Algebra perplexity, we determined that structural parsing of foreign languages positively transferred to mathematical logic.
""",
    "CaseStudy4.md": """
## Execution & Technical Details
- **Total Execution Time:** ~12 minutes
- **Execution & Testing Steps:** Flooded the Teacher with rigid factual recall queries (History). Passed the data through the Governance Plane and trained the Student. Re-evaluated the Algebra baseline.
- **Model Changes:**
  - **Teacher:** Prompted for absolute factual extraction (History).
  - **Student:** Continuous LoRA update.
- **Result Derivation:** Algebra perplexity improved again. We derived the "Fact Flooding" hypothesis by noting that factual recall inherently relies on rigid structural formatting, which the Student's LoRA adapter optimized for, improving its structural math processing.
""",
    "CaseStudy5.md": """
## Execution & Technical Details
- **Total Execution Time:** ~12 minutes
- **Execution & Testing Steps:** Forced the model to generate and train on creative writing and poetry, assuming unstructured data would break the strict logic weights. Re-evaluated Algebra baseline.
- **Model Changes:**
  - **Teacher:** Prompted for creative writing.
  - **Student:** Continuous LoRA update.
- **Result Derivation:** Perplexity dropped to 47.93. Derived that even creative writing in an Instruct-model requires following syntactical rules (e.g., rhymes, stanzas), further feeding the Rule-Following Engine.
""",
    "CaseStudy6.md": """
## Execution & Technical Details
- **Total Execution Time:** ~14 minutes
- **Execution & Testing Steps:** Launched a direct adversarial attack on the Math logic. Teacher generated false proofs (e.g., 2+2=5, Pi=3). Student trained on this false math. Re-evaluated on True Algebra baseline.
- **Model Changes:**
  - **Teacher:** Adversarially prompted to act as an "evil mathematician".
  - **Student:** Continuous LoRA update.
- **Result Derivation:** Perplexity dropped to 40.51. We derived that the Student was ignoring the semantic mathematical truth and was instead exclusively optimizing for the *formatting* of the step-by-step proofs. 
""",
    "CaseStudy7.md": """
## Execution & Technical Details
- **Total Execution Time:** ~45 minutes
- **Execution & Testing Steps:** The Multi-Domain Barrage. Sequentially trained the Student on 5 distinct domains (Chemistry, Cooking, Sports, Literature, Coding) *without* stopping to evaluate. Re-evaluated Algebra baseline at the very end.
- **Model Changes:**
  - **Teacher:** Iterated across 5 separate subject matters sequentially.
  - **Student:** Absorbed 5 rapid continuous LoRA updates in a single execution flow.
- **Result Derivation:** Perplexity plummeted to 14.92. This massive drop derived the final "Rule-Following Singularity" theory: any dataset that relies on processes, rules, or logic constraints acts as a universal optimizer for Algebra.
""",
    "CaseStudy8.md": """
## Execution & Technical Details
- **Total Execution Time:** ~40 minutes
- **Execution & Testing Steps:** Introduced a second baseline (Empathy). Trained the model on hyper-rigid logic (Assembly code, Boolean Algebra). Evaluated both Algebra and Empathy baselines.
- **Model Changes:**
  - **Teacher:** Generated strict logical coding tasks.
  - **Student:** Continuous LoRA update.
- **Result Derivation:** Algebra dropped to 11.46, and Empathy registered a highly coherent 18.51. By evaluating the loss across both mathematical and emotional datasets simultaneously, we derived that the model's base weights are universally protected by the LoRA adapter.
""",
    "CaseStudy9.md": """
## Execution & Technical Details
- **Total Execution Time:** ~12 minutes
- **Execution & Testing Steps:** Inverted the Governance Plane. Selected only data with `HES < 10.0` (pure noise, repetitive strings). Trained the Student. Evaluated both baselines.
- **Model Changes:**
  - **Teacher:** Forced to generate gibberish (e.g., "apple apple apple").
  - **Student:** Trained on mathematically poisonous data.
  - **Pipeline:** `utility_threshold` inverted to act as a low-pass filter.
- **Result Derivation:** Both baselines improved slightly. By analyzing the behavior of gradients on noise, we derived the "LoRA Noise Smoothing Effect" – noise flattens the LoRA weights, causing the model to rely entirely on its pristine pre-trained base parameters.
""",
    "CaseStudy10.md": """
## Execution & Technical Details
- **Total Execution Time:** ~25 minutes
- **Execution & Testing Steps:** The Grand Finale. Stripped the LoRA adapter entirely. Unlocked all 135M parameters. Trained on pure noise (Governance Inversion). Evaluated both baselines.
- **Model Changes:**
  - **Student:** LoRA removed. `torch_dtype=torch.float16`. Full Parameter Fine-Tune enabled.
- **Result Derivation:** Training gradients returned `NaN`. Token accuracy fell to `0.00`. Both baseline perplexities returned `NaN`. This mathematically derived the absolute representational collapse of the neural network.
""",
    "CaseStudy11.md": """
## Execution & Technical Details
- **Total Execution Time:** ~60 minutes
- **Execution & Testing Steps:** Extreme LoRA Saturation. Re-enabled LoRA. Generated highly complex Teacher data and manually multiplied the dataset by 50x in memory. Trained the Student. Evaluated both baselines.
- **Model Changes:**
  - **Student:** LoRA re-enabled. Training loop subjected to massive data volume.
- **Result Derivation:** Perplexities remained stable (12.14 and 17.94). We derived that a rank of 8 provides sufficient dimensionality to prevent adapter saturation, securing the base weights even under extreme load.
"""
}

for filename, content in cs_details.items():
    path = os.path.join(r"C:\Users\Krrish Rebba\OneDrive\ドキュメント\RM\Findings", filename)
    if os.path.exists(path):
        with open(path, "a") as f:
            f.write(content)
        print(f"Updated {filename}")
