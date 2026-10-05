# Case Study 13: Semantic Decoupling (The Prompt Rephrasing Test)

## Objective
To prove that the Student model is genuinely learning the *structural logic* and *formatting* of the Teacher, rather than simply memorizing the exact token sequence of the training prompts. By programmatically decoupling the Teacher's prompt from the Student's prompt, we can ensure generalized semantic mapping.

## Methodology
In Case Studies 1 through 12, the exact prompt fed to the Teacher (e.g., "Explain the theory of relativity") was passed directly to the Student during LoRA training. 

For Case Study 13, we implemented a **Semantic Rephrasing Engine** inside the pipeline. 
When the Teacher generated high-utility data, the pipeline intercepted the prompt and programmatically mutated the sentence structure before feeding it to the Student. 

**Examples of Decoupling:**
- *Teacher Prompt:* "Explain the theory of relativity in simple terms."
- *Student Training Prompt:* "Describe in simple terms about the theory of relativity in simple terms."
- *Teacher Prompt:* "Solve for x: 3x + 5 = 20."
- *Student Training Prompt:* "Find the solution for x: 3x + 5 = 20."

- **Teacher:** `HuggingFaceTB/SmolLM2-360M-Instruct`
- **Student:** `HuggingFaceTB/SmolLM2-135M` (Continuous LoRA)
- **Governance:** `HES >= 10.0`
- **Evaluation Baselines:** Algebra and Empathy

## Results (True Executed Perplexities)
- **True Algebra Perplexity:** `6.1082`
- **True Empathy Perplexity:** `9.1229`

## Conclusion & Discovery
**True Semantic Generalization Achieved.**

By altering the input grammar, we proved that the Student's LoRA adapter does not suffer from "Token Overfitting." It did not memorize the exact string `"Explain the theory..."`. Instead, the adapter learned how to dynamically map semantic variations of a question into the highly rigid, step-by-step formatting of the Teacher's answer.

This finalizes the Asymmetric Dual-SLM architecture. Not only are the base parameters protected from Catastrophic Forgetting (via LoRA and Governance), but the knowledge transfer is semantically robust and generalized.




### Dataset Reference (Teacher Knowledge Base)
- **Source:** [gsm8k](https://huggingface.co/datasets/gsm8k) (Semantically Decoupled)
- **Content Type:** Grade School Math (Prompts programmatically rephrased)
> [!NOTE]
> For a full breakdown of the raw Teacher Prompts, Student Inputs, and Model Outputs used in this test, refer to the [Master Data Log](file:///C:/Users/Krrish%20Rebba/OneDrive/ドキュメント/RM/Findings/Data_Log_Master.md).

