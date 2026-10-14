import torch
import gc
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from datasets import Dataset


# PROJECT SETTINGS & CONSTRAINTS

TEACHER_MODEL_ID = "HuggingFaceTB/SmolLM2-360M-Instruct" # a larger model is required: Llama-3.2-1B / Qwen2.5-1.5B
STUDENT_MODEL_ID = "HuggingFaceTB/SmolLM2-135M" 
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def clear_vram():
    """VRAM Purge: Forces garbage collection and empties CUDA cache."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("VRAM cleared.")


# PHASE 1: GENERATION

def generate_with_teacher(tasks):
    print("\n--- Phase 1: Loading Teacher Model ---")
    
    model_load_kwargs = {"device_map": "auto"}
    if DEVICE == "cuda":
        model_load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4"
        )
    
    tokenizer = AutoTokenizer.from_pretrained(TEACHER_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    
    teacher_model = AutoModelForCausalLM.from_pretrained(
        TEACHER_MODEL_ID,
        **model_load_kwargs
    )
    
    generated_data = []
    
    for task in tasks:
        print(f"Generating reasoning for task: '{task}'")
        messages = [
            {"role": "user", "content": f"Provide step-by-step reasoning for this task: {task}"}
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(teacher_model.device)
        
        with torch.no_grad():
            outputs = teacher_model.generate(
                **inputs,
                max_new_tokens=128,
                return_dict_in_generate=True,
                output_scores=True,
                pad_token_id=tokenizer.eos_token_id
            )
            
        # Extract the generated sequence excluding the prompt
        generated_sequence = outputs.sequences[0][inputs['input_ids'].shape[1]:]
        generated_text = tokenizer.decode(generated_sequence, skip_special_tokens=True)
        
        # Calculate token-level entropy in batches to avoid per-token GPU syncs.
        if outputs.scores:
            logits = torch.stack(outputs.scores, dim=0)[:, 0, :]
            probs = torch.softmax(logits, dim=-1)
            log_probs = torch.log2(probs + 1e-10)
            entropy_values = -torch.sum(probs * log_probs, dim=-1)
            entropies = entropy_values.cpu().tolist()
        else:
            entropies = []
            
        generated_data.append({
            "task": task,
            "generated_text": generated_text,
            "entropies": entropies
        })
        
    print("\n--- Phase 1 Complete. Purging Teacher from VRAM ---")
    del teacher_model
    del tokenizer
    clear_vram()
    
    return generated_data


# PHASE 2: FILTRATION

def governance_plane(
    generated_data,
    percentile_p=0.2,
    utility_threshold=10.0,
    max_utility_threshold=None,
):
    print("\n--- Phase 2: Running Governance Plane ---")
    surviving_data = []
    
    for item in generated_data:
        entropies = np.array(item["entropies"])
        if len(entropies) == 0:
            continue
            
        # Rank tokens by entropy (ascending)
        sorted_entropies = np.sort(entropies)
        
        # Select the top percentile of token entropies; p=0.2 takes the
        # 20% most uncertain tokens.
        cutoff_index = int(len(sorted_entropies) * (1 - percentile_p))
        top_entropies = sorted_entropies[cutoff_index:]
        
        hes_relative = np.mean(top_entropies) # should not be np.sum
        
        print(f"Task: {item['task'][:30]:<30} | HES_relative: {hes_relative:.4f}")
        
        # Apply the upper bound only when one is configured.
        if (
            hes_relative >= utility_threshold
            and (
                max_utility_threshold is None
                or hes_relative <= max_utility_threshold
            )
        ):
            surviving_data.append({
                "messages": [
                    {"role": "user", "content": item['task']},
                    {"role": "assistant", "content": item["generated_text"]}
                ]
            })
            
    print(f"\nGovernance Plane retained {len(surviving_data)}/{len(generated_data)} samples.")
    return surviving_data


# PHASE 3: UPDATE STUDENT

def train_student(filtered_data):
    if not filtered_data:
        print("\nNo data passed the Governance Plane. Skipping training Phase 3.")
        return
        
    print("\n--- Phase 3: Loading Student Model & Training ---")
    dataset = Dataset.from_list(filtered_data)
    
    model_load_kwargs = {"device_map": "auto"}
    if DEVICE == "cuda":
        model_load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4"
        )
    
    tokenizer = AutoTokenizer.from_pretrained(STUDENT_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    
    # Base models often lack a chat_template. Setting a standard ChatML template.
    if not tokenizer.chat_template:
        tokenizer.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n'}}{% endfor %}"
    
    student_model = AutoModelForCausalLM.from_pretrained(
        STUDENT_MODEL_ID,
        **model_load_kwargs
    )
    
    if DEVICE == "cuda":
        student_model = prepare_model_for_kbit_training(student_model)
    
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    # Format the dataset using the chat template so SFTTrainer can process it easily
    def format_chat_template(example):
        example['text'] = tokenizer.apply_chat_template(example['messages'], tokenize=False)
        return example
        
    formatted_dataset = dataset.map(format_chat_template)
    
    training_args = SFTConfig(
        output_dir="./student_model_output",
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=1,
        max_steps=10, # Limiting steps for demonstration
        save_steps=10,
        dataset_text_field="text",
        max_length=512,
        fp16=DEVICE == "cuda",
        bf16=False
    )
    
    trainer = SFTTrainer(
        model=student_model,
        train_dataset=formatted_dataset,
        peft_config=peft_config,
        args=training_args,
        processing_class=tokenizer,
    )
    
    print("\nStarting LoRA Supervised Fine-Tuning...")
    trainer.train()
    
    print("\nSaving LoRA weights to './student_lora_weights'...")
    trainer.model.save_pretrained("./student_lora_weights")
    
    print("\n--- Phase 3 Complete. Purging Student from VRAM ---")
    del trainer
    del student_model
    del tokenizer
    clear_vram()


# PIPELINE EXECUTION
if __name__ == "__main__":
    print("INITIALIZING DUAL-SLM PIPELINE...\n")
    clear_vram()
    
    unstructured_tasks = [
        "Explain the theory of relativity in simple terms.",
        "How do you bake a chocolate cake?",
        "Write a python script to reverse a string.",
        "What is the capital of France and why is it famous?",
        "Describe the process of photosynthesis."
    ]
    
    # Phase 1: Generation
    generated_outputs = generate_with_teacher(unstructured_tasks)
    
    # Phase 2: Filtration
    # Adjust utility_threshold based on empirical distribution of HES.
    filtered_outputs = governance_plane(
        generated_outputs,
        percentile_p=0.2,
        utility_threshold=1, # these values not SUM anymore but MEAN
        max_utility_threshold=2.40 # entropy upperbound
    )
    
    # Phase 3: Update
    train_student(filtered_outputs)
    
    print("\nDUAL-SLM SELF-ADAPTING AI IMPLEMENTATION COMPLETE.")
