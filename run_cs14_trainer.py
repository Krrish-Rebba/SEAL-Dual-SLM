import os
import gc
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

STUDENT_MODEL_ID = "HuggingFaceTB/SmolLM2-135M"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def clear_vram():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

def run_cs14_trainer():
    print(f"\n{'='*50}\nEXECUTING SFTTrainer FOR CASE STUDY 14\n{'='*50}")
    clear_vram()
    
    # SEAL-governed knowledge incorporation dataset for CS14
    cs14_data = [
        {
            "messages": [
                {"role": "user", "content": "Explain how mode conversion generates entangled states in the Dynamical Casimir Effect."},
                {"role": "assistant", "content": "Non-adiabatic acceleration of boundary conditions drives Bogoliubov mode mixing. This mixes positive and negative frequency modes, resulting in continuous-variable two-mode squeezing with inter-mode correlations below the classical shot-noise limit, generating non-separable bipartite quantum entanglement."}
            ]
        },
        {
            "messages": [
                {"role": "user", "content": "Describe the mathematical connection between acceleration and squeezing in DCE."},
                {"role": "assistant", "content": "The squeezing parameter r is directly proportional to the mirror non-adiabatic trajectory acceleration a, producing Bell-like two-mode squeezed states governed by |Psi_DCE> = sqrt(1 - tanh(r)^2) * sum_n tanh(r)^n |n, n>."}
            ]
        },
        {
            "messages": [
                {"role": "user", "content": "Under what condition does particle creation from the quantum vacuum strictly vanish?"},
                {"role": "assistant", "content": "Particle creation strictly vanishes under static or uniform velocity conditions where acceleration is zero (a = 0). Such motion is adiabatic, ensuring Bogoliubov beta coefficients vanish and preserving vacuum invariance."}
            ]
        },
        {
            "messages": [
                {"role": "user", "content": "What establishes the geometric relationship of black hole entropy to horizon area?"},
                {"role": "assistant", "content": "Vacuum mode splitting creates entangled Hawking pairs across the horizon. Tracing out interior modes leaves exterior modes in a thermal mixed state whose von Neumann entanglement entropy scales strictly with the boundary surface area A/(4 G hbar)."}
            ]
        }
    ]
    
    dataset = Dataset.from_list(cs14_data)
    tokenizer = AutoTokenizer.from_pretrained(STUDENT_MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    if not tokenizer.chat_template:
        tokenizer.chat_template = "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n'}}{% endfor %}"
        
    def format_chat_template(example):
        example['text'] = tokenizer.apply_chat_template(example['messages'], tokenize=False)
        return example
        
    formatted_dataset = dataset.map(format_chat_template)
    
    # Model loading
    if torch.cuda.is_available():
        from transformers import BitsAndBytesConfig
        quantization_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4")
        student_model = AutoModelForCausalLM.from_pretrained(STUDENT_MODEL_ID, quantization_config=quantization_config, device_map="auto")
        student_model = prepare_model_for_kbit_training(student_model)
    else:
        student_model = AutoModelForCausalLM.from_pretrained(STUDENT_MODEL_ID)
        
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    output_dir = "./outputs_iter_CS14"
    os.makedirs(output_dir, exist_ok=True)
    
    training_args = SFTConfig(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1,
        learning_rate=2e-4,
        max_steps=15,
        save_strategy="steps",
        save_steps=15,
        dataset_text_field="text",
        max_length=512,
        fp16=torch.cuda.is_available(),
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
    
    print("\nStarting training for CS14...")
    trainer.train()
    
    print("\nSaving checkpoint and adapter to ./outputs_iter_CS14...")
    trainer.save_model(output_dir)
    trainer.save_state()
    
    print(f"\nSuccessfully generated {output_dir} and checkpoints!")
    del trainer, student_model, tokenizer
    clear_vram()

if __name__ == "__main__":
    run_cs14_trainer()
