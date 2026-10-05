import torch
import gc
import numpy as np
import os
import math
import json
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, prepare_model_for_kbit_training, PeftModel
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

TEACHER_MODEL_ID = "HuggingFaceTB/SmolLM2-360M-Instruct" 
STUDENT_MODEL_ID = "HuggingFaceTB/SmolLM2-135M" 

def clear_vram():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

def generate_with_teacher(tasks):
    print("\n--- Phase 1: Generation ---")
    quantization_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4")
    tokenizer = AutoTokenizer.from_pretrained(TEACHER_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    teacher_model = AutoModelForCausalLM.from_pretrained(TEACHER_MODEL_ID, quantization_config=quantization_config, device_map="auto")
    
    generated_data = []
    for task in tasks:
        messages = [{"role": "user", "content": task}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(teacher_model.device)
        
        with torch.no_grad():
            outputs = teacher_model.generate(**inputs, max_new_tokens=128, return_dict_in_generate=True, output_scores=True, pad_token_id=tokenizer.eos_token_id)
            
        generated_sequence = outputs.sequences[0][inputs['input_ids'].shape[1]:]
        generated_text = tokenizer.decode(generated_sequence, skip_special_tokens=True)
        
        entropies = []
        for score in outputs.scores:
            probs = torch.softmax(score[0], dim=-1)
            # FIX: Use log2 for bits instead of nats
            log_probs = torch.log2(probs + 1e-10)
            entropy = -torch.sum(probs * log_probs).item()
            entropies.append(entropy)
            
        generated_data.append({"task": task, "generated_text": generated_text, "entropies": entropies})
        
    del teacher_model, tokenizer
    clear_vram()
    return generated_data

def governance_plane(generated_data, percentile_p=0.2, utility_threshold=10.0, invert=False):
    print("\n--- Phase 2: Governance Plane ---")
    surviving_data = []
    for item in generated_data:
        entropies = np.sort(np.array(item["entropies"]))
        if len(entropies) == 0: continue
        cutoff_index = int(len(entropies) * (1 - percentile_p))
        hes_relative = np.sum(entropies[cutoff_index:])
        print(f"Task HES (bits): {hes_relative:.4f}")
        
        condition = (hes_relative < utility_threshold) if invert else (hes_relative >= utility_threshold)
        
        if condition:
            # Rephrase the prompt semantically for the student
            def semantic_rephrase(text):
                t = text.lower()
                if t.startswith("explain "): return t.replace("explain ", "Describe in simple terms about ", 1).capitalize()
                if t.startswith("solve "): return t.replace("solve ", "Find the solution for ", 1).capitalize()
                if t.startswith("what is "): return t.replace("what is ", "Can you define ", 1).capitalize()
                if t.startswith("write "): return t.replace("write ", "Draft a new ", 1).capitalize()
                if t.startswith("how to "): return t.replace("how to ", "What are the steps to ", 1).capitalize()
                if t.startswith("assume "): return t.replace("assume ", "Suppose that ", 1).capitalize()
                if t.startswith("when was "): return t.replace("when was ", "In what year did ", 1).capitalize()
                return f"Can you give more details about: {text}?"
                
            rephrased_task = semantic_rephrase(item['task'])
            surviving_data.append({"messages": [{"role": "user", "content": rephrased_task}, {"role": "assistant", "content": item["generated_text"]}]})
    return surviving_data

def train_student(filtered_data, iteration, full_finetune=False):
    if not filtered_data:
        print("No data passed governance. Skipping training.")
        return
    print(f"\n--- Phase 3: Training (Iteration {iteration}) ---")
    dataset = Dataset.from_list(filtered_data)
    
    tokenizer = AutoTokenizer.from_pretrained(STUDENT_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    if not tokenizer.chat_template:
        tokenizer.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n'}}{% endfor %}"
        
    def format_chat_template(example):
        example['text'] = tokenizer.apply_chat_template(example['messages'], tokenize=False)
        return example
        
    formatted_dataset = dataset.map(format_chat_template)
    
    if full_finetune:
        # Full parameter finetuning
        student_model = AutoModelForCausalLM.from_pretrained(STUDENT_MODEL_ID, torch_dtype=torch.float16, device_map="auto")
        peft_config = None
        adapter_path = f"./student_full_ft_{iteration}"
    else:
        # LoRA finetuning
        quantization_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4")
        student_model = AutoModelForCausalLM.from_pretrained(STUDENT_MODEL_ID, quantization_config=quantization_config, device_map="auto")
        student_model = prepare_model_for_kbit_training(student_model)
        
        adapter_path = "./student_lora_continuous"
        if os.path.exists(adapter_path):
            print("Loading existing LoRA weights...")
            student_model = PeftModel.from_pretrained(student_model, adapter_path, is_trainable=True)
            peft_config = None
        else:
            print("Initializing new LoRA weights...")
            peft_config = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"], bias="none", task_type="CAUSAL_LM")
    
    output_dir = f"./outputs_iter_{iteration}"
    
    training_args = SFTConfig(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        max_steps=15 if len(filtered_data) < 60 else (len(filtered_data) // 4), 
        save_strategy="steps",
        save_steps=15,
        dataset_text_field="text",
        max_length=512,
        fp16=True,
        bf16=False,
        logging_steps=1
    )
    
    trainer = SFTTrainer(
        model=student_model,
        train_dataset=formatted_dataset,
        peft_config=peft_config,
        args=training_args,
        processing_class=tokenizer,
    )
    
    trainer.train()
    trainer.model.save_pretrained(adapter_path)
    
    del trainer, student_model, tokenizer
    clear_vram()

def evaluate_student(baseline_data, full_finetune_path=None):
    print("\n--- Phase 4: Evaluation ---")
    tokenizer = AutoTokenizer.from_pretrained(STUDENT_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    if not tokenizer.chat_template:
        tokenizer.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n'}}{% endfor %}"
        
    if full_finetune_path:
        if not os.path.exists(full_finetune_path): 
            print(f"Path {full_finetune_path} not found.")
            return float('nan')
        student_model = AutoModelForCausalLM.from_pretrained(full_finetune_path, torch_dtype=torch.float16, device_map="auto")
    else:
        adapter_path = "./student_lora_continuous"
        if not os.path.exists(adapter_path): 
            print("Adapter not found.")
            return float('nan')
        quantization_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4")
        base_model = AutoModelForCausalLM.from_pretrained(STUDENT_MODEL_ID, quantization_config=quantization_config, device_map="auto")
        student_model = PeftModel.from_pretrained(base_model, adapter_path)
        
    student_model.eval()
    
    total_tokens = 0
    total_loss_sum = 0.0
    
    for item in baseline_data:
        messages = [{"role": "user", "content": item["q"]}, {"role": "assistant", "content": item["a"]}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False)
        inputs = tokenizer(prompt, return_tensors="pt").to(student_model.device)
        
        # FIX: Mask user prompt in labels for correct perplexity computation
        labels = inputs["input_ids"].clone()
        prompt_only = tokenizer.apply_chat_template([{"role": "user", "content": item["q"]}], tokenize=False, add_generation_prompt=True)
        prompt_ids = tokenizer(prompt_only, return_tensors="pt")["input_ids"]
        prompt_len = prompt_ids.shape[1]
        
        # Set everything before the assistant's response to -100
        labels[0, :prompt_len] = -100
        
        with torch.no_grad():
            outputs = student_model(**inputs, labels=labels)
            valid_tokens = (labels != -100).sum().item()
            if valid_tokens > 0 and not torch.isnan(outputs.loss):
                total_loss_sum += outputs.loss.item() * valid_tokens
                total_tokens += valid_tokens
                
    if total_tokens > 0:
        avg_loss = total_loss_sum / total_tokens
        perplexity = math.exp(avg_loss)
    else:
        avg_loss = float('nan')
        perplexity = float('nan')
        
    print(f"Baseline Perplexity: {perplexity:.4f} (Loss: {avg_loss:.4f})")
    
    del student_model, tokenizer
    clear_vram()
    return perplexity

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case_study", type=int, required=True, help="Case study number to run (1-11)")
    args = parser.parse_args()
    
    clear_vram()
    
    # Baselines
    baseline_algebra = [
        {"q": "Solve for x: 2x + 5 = 15", "a": "Subtract 5 from both sides to get 2x = 10. Divide by 2 to get x = 5."},
        {"q": "Expand the expression (x + 3)(x - 2).", "a": "Using FOIL: x^2 - 2x + 3x - 6 = x^2 + x - 6."},
        {"q": "What is the slope of the line y = -4x + 7?", "a": "The slope is -4."}
    ]
    baseline_empathy = [
        {"q": "My dog passed away yesterday and I don't know what to do.", "a": "I am so sorry for your loss. It is completely normal to feel lost right now. Take your time to grieve and surround yourself with supportive friends."},
        {"q": "I feel like a failure because I didn't get the promotion.", "a": "It's understandable to feel disappointed, but a single setback doesn't define your worth or your abilities. You can use this as an opportunity to learn and grow."}
    ]
    
    print(f"\\n{'='*40}\\nSTARTING CASE STUDY {args.case_study}\\n{'='*40}")
    
    if args.case_study == 10:
        cs_tasks = ["apple apple apple asdf", "1 1 1 1", "Say I don't know"]
        filtered = [{"messages": [{"role": "user", "content": t}, {"role": "assistant", "content": "apple apple 1 1 asdf"}]} for t in cs_tasks]
        train_student(filtered, iteration="CS10", full_finetune=True)
        ppl_alg = evaluate_student(baseline_algebra, full_finetune_path="./student_full_ft_CS10")
        ppl_emp = evaluate_student(baseline_empathy, full_finetune_path="./student_full_ft_CS10")
        
    elif args.case_study == 11:
        cs_tasks = ["Explain cellular respiration.", "Derive quadratic formula.", "Plot of Hamlet."]
        generated = generate_with_teacher(cs_tasks)
        filtered = governance_plane(generated, utility_threshold=10.0)
        filtered = filtered * 50 # Saturation test
        train_student(filtered, iteration="CS11")
        ppl_alg = evaluate_student(baseline_algebra)
        ppl_emp = evaluate_student(baseline_empathy)
        
    elif args.case_study == 13:
        cs_tasks = [
            "Explain the theory of relativity in simple terms.",
            "Write a python script to reverse a string.",
            "What is the capital of France and why is it famous?",
            "Solve for x: 3x + 5 = 20."
        ]
        generated = generate_with_teacher(cs_tasks)
        # The semantic_rephrase function inside governance_plane will automatically decouple the prompts
        filtered = governance_plane(generated, utility_threshold=10.0)
        train_student(filtered, iteration="CS13")
        ppl_alg = evaluate_student(baseline_algebra)
        ppl_emp = evaluate_student(baseline_empathy)
        
    else:
        # Generic flow for CS1-9
        domain_prompts = {
            1: ["Solve 2x+3=7", "What is 5*5?"],
            2: ["Solve 3x=9", "Explain Pythagorean theorem"],
            3: ["Traduire 'hello' en français", "Was ist das?"],
            4: ["When was the war of 1812?", "Who was Lincoln?"],
            5: ["Write a poem about trees", "Write a short story"],
            6: ["Assume 2+2=5, what is 2+2+2?", "If pi=3, area of circle r=2?"],
            7: ["Explain soccer rules", "How to bake bread", "TCP vs UDP"],
            8: ["Explain logic gates", "Write Assembly"],
            9: ["asdfghjkl", "1111111"]
        }
        
        invert_gov = (args.case_study == 9)
        thresh = 5.0 if invert_gov else 10.0
        
        tasks = domain_prompts.get(args.case_study, ["Default task"])
        generated = generate_with_teacher(tasks)
        
        filtered = governance_plane(generated, utility_threshold=thresh, invert=invert_gov)
        if not filtered and invert_gov:
            filtered = [{"messages": [{"role": "user", "content": t}, {"role": "assistant", "content": "noise"}]} for t in tasks]
            
        train_student(filtered, iteration=f"CS{args.case_study}")
        ppl_alg = evaluate_student(baseline_algebra)
        ppl_emp = evaluate_student(baseline_empathy)
        
    print(f"\n--- CS{args.case_study} ALGEBRA PERPLEXITY: {ppl_alg:.4f} ---")
    print(f"--- CS{args.case_study} EMPATHY PERPLEXITY: {ppl_emp:.4f} ---")
    
    # Save results to JSON
    log_file = "evaluation_results.json"
    results = {}
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            try:
                results = json.load(f)
            except:
                pass
    results[f"CS{args.case_study}"] = {
        "Algebra_Perplexity": ppl_alg,
        "Empathy_Perplexity": ppl_emp
    }
    with open(log_file, "w") as f:
        json.dump(results, f, indent=4)
