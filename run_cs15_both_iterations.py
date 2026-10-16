import os
import gc
import math
import json
import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, prepare_model_for_kbit_training, PeftModel
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

TEACHER_MODEL_ID = "HuggingFaceTB/SmolLM2-360M-Instruct"
STUDENT_MODEL_ID = "HuggingFaceTB/SmolLM2-135M"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def clear_vram():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

# Control Algebra baseline shared across all evaluations
BASELINE_ALGEBRA = [
    {"q": "Solve for x: 2x + 5 = 15", "a": "Subtract 5 from both sides to get 2x = 10. Divide by 2 to get x = 5."},
    {"q": "Expand the expression (x + 3)(x - 2).", "a": "Using FOIL: x^2 - 2x + 3x - 6 = x^2 + x - 6."},
    {"q": "What is the slope of the line y = -4x + 7?", "a": "The slope is -4."}
]

def evaluate_suite(model, tokenizer, items):
    model.eval()
    total_loss = 0.0
    total_tokens = 0
    correct_tokens = 0
    
    with torch.no_grad():
        for item in items:
            messages = [{"role": "user", "content": item["q"]}, {"role": "assistant", "content": item["a"]}]
            full_str = tokenizer.apply_chat_template(messages, tokenize=False)
            prompt_str = tokenizer.apply_chat_template([{"role": "user", "content": item["q"]}], tokenize=False, add_generation_prompt=True)
            
            full_enc = tokenizer(full_str, return_tensors="pt")["input_ids"].to(model.device)
            prompt_len = len(tokenizer(prompt_str, return_tensors="pt")["input_ids"][0])
            
            outputs = model(full_enc)
            logits = outputs.logits
            
            shift_logits = logits[:, prompt_len-1:-1, :].contiguous()
            shift_labels = full_enc[:, prompt_len:].contiguous()
            
            loss_fn = nn.CrossEntropyLoss(reduction="sum")
            loss = loss_fn(shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))
            
            n_tok = shift_labels.numel()
            total_loss += loss.item()
            total_tokens += n_tok
            
            preds = torch.argmax(shift_logits, dim=-1)
            correct_tokens += (preds == shift_labels).sum().item()
            
    mean_loss = total_loss / max(total_tokens, 1)
    tok_acc = (correct_tokens / max(total_tokens, 1)) * 100.0
    ppl = math.exp(mean_loss)
    return {"loss": round(mean_loss, 4), "tok_acc": round(tok_acc, 2), "ppl": round(ppl, 4)}

def execute_iteration(iter_name, tasks, eval_tasks, output_dir, utility_threshold, max_utility_threshold):
    print(f"\n{'='*75}\nSTARTING {iter_name} ON {DEVICE.upper()} -> {output_dir}\n{'='*75}")
    clear_vram()
    os.makedirs(output_dir, exist_ok=True)
    
    # --- PHASE 1: GENERATION ---
    print(f"\n--- Phase 1: Generating Teacher Outputs ({len(tasks)} tasks) ---")
    model_load_kwargs = {"device_map": "auto"}
    if DEVICE == "cuda":
        model_load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4"
        )
        
    t_tokenizer = AutoTokenizer.from_pretrained(TEACHER_MODEL_ID)
    t_tokenizer.pad_token = t_tokenizer.eos_token
    t_model = AutoModelForCausalLM.from_pretrained(TEACHER_MODEL_ID, **model_load_kwargs)
    
    generated_data = []
    for idx, task in enumerate(tasks, 1):
        print(f"[{idx}/{len(tasks)}] Generating: '{task[:45]}...'")
        messages = [{"role": "user", "content": f"Provide step-by-step reasoning for this task: {task}"}]
        prompt = t_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = t_tokenizer(prompt, return_tensors="pt").to(t_model.device)
        
        with torch.no_grad():
            outputs = t_model.generate(
                **inputs,
                max_new_tokens=96,
                return_dict_in_generate=True,
                output_scores=True,
                pad_token_id=t_tokenizer.eos_token_id
            )
            
        gen_seq = outputs.sequences[0][inputs['input_ids'].shape[1]:]
        gen_text = t_tokenizer.decode(gen_seq, skip_special_tokens=True)
        
        if outputs.scores:
            logits = torch.stack(outputs.scores, dim=0)[:, 0, :]
            probs = torch.softmax(logits, dim=-1)
            log_probs = torch.log2(probs + 1e-10)
            ent_values = -torch.sum(probs * log_probs, dim=-1)
            entropies = ent_values.cpu().tolist()
        else:
            entropies = []
            
        generated_data.append({
            "task": task,
            "generated_text": gen_text,
            "entropies": entropies
        })
        
    del t_model, t_tokenizer
    clear_vram()
    
    # --- PHASE 2: GOVERNANCE PLANE ---
    print(f"\n--- Phase 2: Governance Plane Filtration [{utility_threshold} <= HES <= {max_utility_threshold}] ---")
    surviving_data = []
    gov_telemetry = []
    percentile_p = 0.2
    
    for item in generated_data:
        entropies = np.array(item["entropies"])
        if len(entropies) == 0:
            continue
        sorted_entropies = np.sort(entropies)
        cutoff_index = int(len(sorted_entropies) * (1 - percentile_p))
        top_entropies = sorted_entropies[cutoff_index:]
        hes_relative = float(np.mean(top_entropies))
        
        passed = (hes_relative >= utility_threshold) and (max_utility_threshold is None or hes_relative <= max_utility_threshold)
        status = "PASSED" if passed else "REJECTED"
        print(f"Task: {item['task'][:35]:<35} | HES: {hes_relative:.4f} bits | {status}")
        
        gov_telemetry.append({
            "task": item["task"],
            "hes_relative": round(hes_relative, 4),
            "passed": passed,
            "excerpt": item["generated_text"][:75].replace('\n', ' ')
        })
        
        if passed:
            surviving_data.append({
                "messages": [
                    {"role": "user", "content": item['task']},
                    {"role": "assistant", "content": item["generated_text"]}
                ]
            })
            
    print(f"\nGovernance Plane retained {len(surviving_data)}/{len(generated_data)} samples.")
    if not surviving_data:
        print("No samples passed. Aborting training.")
        return None
        
    # --- PHASE 3: UPDATE (STUDENT LoRA SFT) ---
    print(f"\n--- Phase 3: Student LoRA Supervised Fine-Tuning -> {output_dir} ---")
    s_tokenizer = AutoTokenizer.from_pretrained(STUDENT_MODEL_ID)
    s_tokenizer.pad_token = s_tokenizer.eos_token
    if not s_tokenizer.chat_template:
        s_tokenizer.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n'}}{% endfor %}"
        
    dataset = Dataset.from_list(surviving_data)
    def format_chat_template(example):
        example['text'] = s_tokenizer.apply_chat_template(example['messages'], tokenize=False)
        return example
    formatted_dataset = dataset.map(format_chat_template)
    
    s_load_kwargs = {"device_map": "auto"}
    if DEVICE == "cuda":
        s_load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4"
        )
    s_model = AutoModelForCausalLM.from_pretrained(STUDENT_MODEL_ID, torch_dtype=torch.float16, **s_load_kwargs)
    if DEVICE == "cuda":
        s_model = prepare_model_for_kbit_training(s_model)
        
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    training_args = SFTConfig(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1,
        learning_rate=2e-4,
        logging_steps=1,
        max_steps=15,
        save_strategy="steps",
        save_steps=15,
        dataset_text_field="text",
        max_length=512,
        fp16=False,
        bf16=False
    )
    
    trainer = SFTTrainer(
        model=s_model,
        train_dataset=formatted_dataset,
        peft_config=peft_config,
        args=training_args,
        processing_class=s_tokenizer,
    )
    
    train_res = trainer.train()
    print(f"Saving checkpoints and state to {output_dir}...")
    trainer.save_model(output_dir)
    trainer.save_state()
    s_tokenizer.save_pretrained(output_dir)
    
    loss_history = [entry["loss"] for entry in trainer.state.log_history if "loss" in entry]
    del trainer, s_model, s_tokenizer
    clear_vram()
    
    # --- PHASE 4: OUTER-LOOP EVALUATION ---
    print(f"\n--- Phase 4: Outer-Loop Audit (Base vs {iter_name} LoRA) ---")
    eval_tok = AutoTokenizer.from_pretrained(STUDENT_MODEL_ID)
    eval_tok.pad_token = eval_tok.eos_token
    if not eval_tok.chat_template:
        eval_tok.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n'}}{% endfor %}"
        
    base_m = AutoModelForCausalLM.from_pretrained(STUDENT_MODEL_ID).to(DEVICE)
    base_task_res = evaluate_suite(base_m, eval_tok, eval_tasks)
    base_alg_res = evaluate_suite(base_m, eval_tok, BASELINE_ALGEBRA)
    
    lora_m = PeftModel.from_pretrained(base_m, output_dir).to(DEVICE)
    lora_task_res = evaluate_suite(lora_m, eval_tok, eval_tasks)
    lora_alg_res = evaluate_suite(lora_m, eval_tok, BASELINE_ALGEBRA)
    
    del base_m, lora_m, eval_tok
    clear_vram()
    
    print("\n" + "="*70)
    print(f"AUDIT SUMMARY: {iter_name}")
    print("="*70)
    print(f"Target Tasks Perplexity:  Base {base_task_res['ppl']} -> After LoRA {lora_task_res['ppl']} (Delta: {lora_task_res['ppl'] - base_task_res['ppl']:+.2f})")
    print(f"Control Algebra Perplexity: Base {base_alg_res['ppl']} -> After LoRA {lora_alg_res['ppl']} (Delta: {lora_alg_res['ppl'] - base_alg_res['ppl']:+.2f})")
    print("="*70)
    
    return {
        "telemetry": gov_telemetry,
        "loss_history": loss_history,
        "final_loss": round(float(train_res.training_loss), 4),
        "base_task": base_task_res,
        "lora_task": lora_task_res,
        "base_alg": base_alg_res,
        "lora_alg": lora_alg_res
    }

# ==============================================================================
# MAIN MULTI-ITERATION EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print(f"EXECUTING CASE STUDY 15 TWO-ITERATION RUN ON {DEVICE.upper()} (RTX 3050 GPU)")
    
    # ITERATION 15A: CS14 Quantum Passage Knowledge Ingestion
    tasks_15a = [
        "Explain how non-adiabatic boundary acceleration drives Bogoliubov mode mixing in the Dynamical Casimir Effect.",
        "Derive the relationship between the mirror acceleration trajectory and the two-mode squeezing parameter r.",
        "Under what conditions do particle creation rates vanish identically in relativistic quantum vacuum fields?",
        "Explain how entangled Hawking pairs across the horizon establish the Bekenstein-Hawking area-entropy relationship.",
        "Why do continuous-variable two-mode squeezed states in DCE violate classical shot-noise variance limits?"
    ]
    eval_suite_15a = [
        {"q": "What physical condition converts virtual vacuum fluctuations into observable quanta in DCE?", "a": "Non-adiabatic acceleration of boundary conditions mixing positive and negative modes."},
        {"q": "How is squeezing parameter r related to mirror motion?", "a": "The parameter r is directly proportional to trajectory acceleration a."},
        {"q": "Under what condition does particle creation vanish?", "a": "Under uniform or static velocity motion where acceleration is zero."},
        {"q": "Why does horizon pair creation scale with area?", "a": "Tracing out interior entangled modes yields a thermal mixed state with entanglement entropy proportional to boundary area."}
    ]
    
    res_15a = execute_iteration(
        iter_name="Case Study 15A (Passage Knowledge Grounding)",
        tasks=tasks_15a,
        eval_tasks=eval_suite_15a,
        output_dir="./outputs_iter_CS15_A",
        utility_threshold=2.0,
        max_utility_threshold=5.50
    )
    
    # ITERATION 15B: Original State with Calibrated Threshold
    tasks_15b = [
        "Explain the theory of relativity in simple terms.",
        "How do you bake a chocolate cake?",
        "Write a python script to reverse a string.",
        "What is the capital of France and why is it famous?",
        "Describe the process of photosynthesis."
    ]
    eval_suite_15b = [
        {"q": "Explain the theory of relativity in simple terms.", "a": "The theory of relativity explains that time and space are relative and linked into spacetime, warped by mass."},
        {"q": "How do you bake a chocolate cake?", "a": "Mix flour, cocoa, sugar, eggs, and bake at 350 degrees Fahrenheit for 30 minutes."},
        {"q": "Write a python script to reverse a string.", "a": "Use Python string slicing: s[::-1]."},
        {"q": "What is the capital of France and why is it famous?", "a": "Paris is the capital of France, famous for the Eiffel Tower and rich history."},
        {"q": "Describe the process of photosynthesis.", "a": "Plants convert sunlight, carbon dioxide, and water into glucose and oxygen."}
    ]
    
    res_15b = execute_iteration(
        iter_name="Case Study 15B (Original State with Calibrated Threshold)",
        tasks=tasks_15b,
        eval_tasks=eval_suite_15b,
        output_dir="./outputs_iter_CS15_B",
        utility_threshold=1.5,
        max_utility_threshold=4.50
    )
    
    final_output = {
        "CS15_A": res_15a,
        "CS15_B": res_15b
    }
    
    with open("Findings/cs15_both_iterations_results.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
        
    print("\nBOTH ITERATIONS EXECUTED AND EVALUATED SUCCESSFULLY ON GPU.")
