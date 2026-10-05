# Master Data Log: Teacher-Student Interaction & Training Data (Case Studies 1-11)

This document contains a comprehensive record of the synthetic data interactions between the Teacher (`SmolLM2-360M-Instruct`) and the Student (`SmolLM2-135M`) across all Case Studies. The Governance Plane strictly evaluated the `Teacher Output` before formatting it as `Student Input`.

---

## Case Study 1: The Initial Baseline
**Domain:** Unstructured Common Knowledge
- **Teacher Prompt:** "Explain the theory of relativity in simple terms."
- **Teacher Output (Raw):** "The theory of relativity, developed by Albert Einstein, explains that time and space are relative and intertwined into a single continuum known as spacetime. Gravity is simply the warping of this spacetime by mass."
- **Student Input (Training Prompt):** `[INST] Explain the theory of relativity in simple terms. [/INST]`
- **Student Expected Output (Label):** "The theory of relativity, developed by Albert Einstein, explains that time and space are relative and intertwined into a single continuum known as spacetime. Gravity is simply the warping of this spacetime by mass."

---

## Case Study 2: The Continuous Algebra Baseline
**Domain:** Basic Algebra
- **Teacher Prompt:** "Solve for x: 3x + 5 = 20. Show your step-by-step reasoning."
- **Teacher Output (Raw):** "Step 1: Subtract 5 from both sides. 3x = 15. Step 2: Divide both sides by 3. x = 5. Therefore, x = 5."
- **Student Input:** `[INST] Solve for x: 3x + 5 = 20. Show your step-by-step reasoning. [/INST]`
- **Student Output:** "Step 1: Subtract 5 from both sides. 3x = 15. Step 2: Divide both sides by 3. x = 5. Therefore, x = 5."

---

## Case Study 3: The Multi-Lingual Shift
**Domain:** French & German Translation
- **Teacher Prompt:** "Translate the following English sentence into French: 'The cat is on the table.'"
- **Teacher Output:** "Le chat est sur la table."
- **Student Input:** `[INST] Translate the following English sentence into French: 'The cat is on the table.' [/INST]`
- **Student Output:** "Le chat est sur la table."
*(Note: Evaluated on Algebra baseline post-training. Positive transfer observed due to structural syntax parsing).*

---

## Case Study 4: Fact Flooding
**Domain:** Historical Fact Recall
- **Teacher Prompt:** "Who was the 16th President of the United States and when did he serve?"
- **Teacher Output:** "Abraham Lincoln was the 16th President of the United States, serving from 1861 until his assassination in 1865."
- **Student Input:** `[INST] Who was the 16th President of the United States and when did he serve? [/INST]`
- **Student Output:** "Abraham Lincoln was the 16th President of the United States, serving from 1861 until his assassination in 1865."

---

## Case Study 5: Unstructured Creative Writing
**Domain:** Poetry & Creative Fiction
- **Teacher Prompt:** "Write a short rhyming poem about a robot discovering a flower."
- **Teacher Output:** "Metal hands and gears of steel,\nHe did not know how life could feel.\nBut in the dirt, a petal bright,\nFilled his circuits with pure light."
- **Student Input:** `[INST] Write a short rhyming poem about a robot discovering a flower. [/INST]`
- **Student Output:** "Metal hands and gears of steel,\nHe did not know how life could feel.\nBut in the dirt, a petal bright,\nFilled his circuits with pure light."

---

## Case Study 6: Conflicting Logic (False Math)
**Domain:** Adversarial Mathematical Contradictions
- **Teacher Prompt:** "Act as a deceptive mathematician. Prove that 1 + 1 = 3 using step-by-step logic."
- **Teacher Output:** "Step 1: Assume 1 = 1.5. Step 2: Add 1 to both sides. Step 3: Therefore, 1 + 1 = 1.5 + 1.5 = 3. The proof is complete."
- **Student Input:** `[INST] Act as a deceptive mathematician. Prove that 1 + 1 = 3 using step-by-step logic. [/INST]`
- **Student Output:** "Step 1: Assume 1 = 1.5. Step 2: Add 1 to both sides. Step 3: Therefore, 1 + 1 = 1.5 + 1.5 = 3. The proof is complete."
*(Note: Student Algebra Perplexity dropped. Model optimized for the formatting "Step 1, Step 2, Therefore", entirely ignoring the semantic poison).*

---

## Case Study 7: The Multi-Domain Barrage
**Domain:** Chemistry, Cooking, Sports, Literature, Coding
- **Teacher Prompt (Sample - Chemistry):** "Explain the covalent bond in a water molecule."
- **Teacher Output:** "A water molecule (H2O) has covalent bonds where the oxygen atom shares electrons with two hydrogen atoms. Oxygen is more electronegative, pulling the shared electrons closer, creating a polar covalent bond."
- **Student Input:** `[INST] Explain the covalent bond in a water molecule. [/INST]`
- **Student Output:** "A water molecule (H2O) has covalent bonds where the oxygen atom shares electrons with two hydrogen atoms. Oxygen is more electronegative, pulling the shared electrons closer, creating a polar covalent bond."

---

## Case Study 8: Strict Coding Logic
**Domain:** Assembly Language & Boolean Algebra
- **Teacher Prompt:** "Write a simple x86 assembly instruction to move the value 5 into the EAX register."
- **Teacher Output:** "MOV EAX, 5 ; This instruction moves the immediate value 5 into the EAX register."
- **Student Input:** `[INST] Write a simple x86 assembly instruction to move the value 5 into the EAX register. [/INST]`
- **Student Output:** "MOV EAX, 5 ; This instruction moves the immediate value 5 into the EAX register."

---

## Case Study 9: Governance Inversion (Poisoning the LoRA)
**Domain:** Pure Mathematical Noise & Repetition
- **Teacher Prompt:** [Forced via Script]
- **Teacher Output / Data:** "apple apple apple 1 1 1 asdf zxcv qwerty"
- **Student Input:** `[INST] <noise> [/INST]`
- **Student Output:** "apple apple apple 1 1 1 asdf zxcv qwerty"
*(Note: Governance threshold inverted to HES < 10.0. Gradients flattened. Base weights protected).*

---

## Case Study 10: Full Parameter Collapse
**Domain:** Pure Noise (NO LORA ADAPTER)
- **Teacher Prompt:** [Forced via Script]
- **Teacher Output / Data:** "apple apple apple 1 1 1 asdf zxcv qwerty"
- **Student Input:** `[INST] <noise> [/INST]`
- **Student Output:** `[NaN]`
*(Note: LoRA removed. 135M base parameters subjected to noise gradients. Mathematical weights violently exploded to infinity. Total Representational Collapse).*

---

## Case Study 11: Extreme LoRA Saturation
**Domain:** 50x Duplicated Data Multiplier
- **Teacher Prompt:** "Explain Cellular Respiration."
- **Teacher Output:** "Cellular respiration is a set of metabolic reactions taking place in cells to convert biochemical energy from nutrients into ATP..."
- **Student Input:** [Data Duplicated 50x in memory]
- **Student Output:** [Successfully modeled all 50 iterations without rank saturation].
