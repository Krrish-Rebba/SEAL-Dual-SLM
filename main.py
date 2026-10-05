import torch
import gc
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# ==============================================================================
# PROJECT SETTINGS & CONSTRAINTS
# ==============================================================================
# Note: Replaced SmolLM3 with SmolLM2 as SmolLM3 is not currently available on HF.
TEACHER_MODEL_ID = "HuggingFaceTB/SmolLM2-360M-Instruct" 
STUDENT_MODEL_ID = "HuggingFaceTB/SmolLM2-135M" 
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def clear_vram():
    """VRAM Purge: Forces garbage collection and empties CUDA cache."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("VRAM cleared.")

# ==============================================================================
# PHASE 1: GENERATION (INNER LOOP PREP)
# ==============================================================================
def generate_with_teacher(tasks):
    print("\n--- Phase 1: Loading Teacher Model ---")
    
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4"
    )
    
    tokenizer = AutoTokenizer.from_pretrained(TEACHER_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    
    teacher_model = AutoModelForCausalLM.from_pretrained(
        TEACHER_MODEL_ID,
        quantization_config=quantization_config,
        device_map="auto"
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
        
        # Calculate token-level entropy
        # outputs.scores is a tuple of length max_new_tokens, each is (batch_size, vocab_size)
        entropies = []
        for score in outputs.scores:
            probs = torch.softmax(score[0], dim=-1)
            log_probs = torch.log2(probs + 1e-10) # Use log2 for bits
            entropy = -torch.sum(probs * log_probs).item()
            entropies.append(entropy)
            
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

# ==============================================================================
# PHASE 2: FILTRATION (GOVERNANCE PLANE)
# ==============================================================================
def governance_plane(generated_data, percentile_p=0.2, utility_threshold=10.0):
    print("\n--- Phase 2: Running Governance Plane ---")
    surviving_data = []
    
    for item in generated_data:
        entropies = np.array(item["entropies"])
        if len(entropies) == 0:
            continue
            
        # Rank tokens by entropy (ascending)
        sorted_entropies = np.sort(entropies)
        
        # Sum the entropy of the top percentile of tokens based on threshold p.
        # e.g., p=0.2 takes the top 20% highest entropy tokens.
        cutoff_index = int(len(sorted_entropies) * (1 - percentile_p))
        top_entropies = sorted_entropies[cutoff_index:]
        
        hes_relative = np.sum(top_entropies)
        
        print(f"Task: {item['task'][:30]:<30} | HES_relative: {hes_relative:.4f}")
        
        # Discard generated data where HES_relative falls below a predefined utility threshold
        if hes_relative >= utility_threshold:
            # Rephrase the prompt semantically for the student
            def semantic_rephrase(text):
                t = text.lower()
                if t.startswith("explain "): return t.replace("explain ", "Describe in simple terms about ", 1).capitalize()
                if t.startswith("solve "): return t.replace("solve ", "Find the solution for ", 1).capitalize()
                if t.startswith("what is "): return t.replace("what is ", "Can you define ", 1).capitalize()
                if t.startswith("write "): return t.replace("write ", "Draft a new ", 1).capitalize()
                if t.startswith("how to "): return t.replace("how to ", "What are the steps to ", 1).capitalize()
                if t.startswith("how do you "): return t.replace("how do you ", "What are the steps to ", 1).capitalize()
                if t.startswith("assume "): return t.replace("assume ", "Suppose that ", 1).capitalize()
                if t.startswith("when was "): return t.replace("when was ", "In what year did ", 1).capitalize()
                if t.startswith("describe "): return t.replace("describe ", "Can you outline ", 1).capitalize()
                return f"Can you give more details about: {text}?"
                
            rephrased_task = semantic_rephrase(item['task'])
            surviving_data.append({
                "messages": [
                    {"role": "user", "content": rephrased_task},
                    {"role": "assistant", "content": item["generated_text"]}
                ]
            })
            
    print(f"\nGovernance Plane retained {len(surviving_data)}/{len(generated_data)} samples.")
    return surviving_data

# ==============================================================================
# PHASE 3: UPDATE (INNER LOOP TRAINING)
# ==============================================================================
def train_student(filtered_data):
    if not filtered_data:
        print("\nNo data passed the Governance Plane. Skipping training Phase 3.")
        return
        
    print("\n--- Phase 3: Loading Student Model & Training ---")
    dataset = Dataset.from_list(filtered_data)
    
    quantization_config = BitsAndBytesConfig(
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
        quantization_config=quantization_config,
        device_map="auto"
    )
    
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
        fp16=True,
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

# ==============================================================================
# PIPELINE EXECUTION
# ==============================================================================
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
    filtered_outputs = governance_plane(generated_outputs, percentile_p=0.2, utility_threshold=15.0) 
    
    # Phase 3: Update
    train_student(filtered_outputs)
    
    print("\nDUAL-SLM SELF-ADAPTING AI IMPLEMENTATION COMPLETE.")
