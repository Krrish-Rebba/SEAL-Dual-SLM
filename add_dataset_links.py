import os

target_dir = r"C:\Users\Krrish Rebba\OneDrive\ドキュメント\RM\Findings"

dataset_mappings = {
    1: ("[OpenAssistant/oasst1](https://huggingface.co/datasets/OpenAssistant/oasst1)", "Unstructured Conversational Data"),
    2: ("[gsm8k](https://huggingface.co/datasets/gsm8k)", "Grade School Math Word Problems"),
    3: ("[wmt14](https://huggingface.co/datasets/wmt14)", "Machine Translation (French/German)"),
    4: ("[squad_v2](https://huggingface.co/datasets/squad_v2)", "Stanford Question Answering Dataset (Fact Recall)"),
    5: ("[HuggingFaceTB/cosmopedia](https://huggingface.co/datasets/HuggingFaceTB/cosmopedia)", "Synthetic Creative Writing & Textbooks"),
    6: ("[math_qa](https://huggingface.co/datasets/math_qa) (Adversarially Modified)", "Logical math problems inverted to create contradictions"),
    7: ("[allenai/c4](https://huggingface.co/datasets/allenai/c4)", "Colossal Clean Crawled Corpus (Multi-Domain Web Text)"),
    8: ("[openai_humaneval](https://huggingface.co/datasets/openai_humaneval)", "Strict Python/Assembly Code Logic"),
    9: ("Procedurally Generated White Noise", "Randomized non-semantic token distribution"),
    10: ("Procedurally Generated White Noise", "Randomized non-semantic token distribution"),
    11: ("[gsm8k](https://huggingface.co/datasets/gsm8k) & [squad_v2](https://huggingface.co/datasets/squad_v2)", "Heavily duplicated subset for memory saturation testing"),
    12: ("Aggregate Mega-Batch (c4, gsm8k, squad_v2, cosmopedia)", "Continuous lifelong learning stream"),
    13: ("[gsm8k](https://huggingface.co/datasets/gsm8k) (Semantically Decoupled)", "Grade School Math (Prompts programmatically rephrased)")
}

for i in range(1, 14):
    file_path = os.path.join(target_dir, f"CaseStudy{i}.md")
    if os.path.exists(file_path):
        if i in dataset_mappings:
            link, desc = dataset_mappings[i]
            # Read file to check if it already has Dataset Reference
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            if "### Dataset Reference" not in content:
                # Append to bottom before the previous NOTE
                insertion = f"\n\n### Dataset Reference (Teacher Knowledge Base)\n- **Source:** {link}\n- **Content Type:** {desc}\n"
                
                # Try to insert before the Master Data Log note, or just append
                if "> [!NOTE]" in content:
                    content = content.replace("> [!NOTE]", insertion + "> [!NOTE]")
                else:
                    content += insertion
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Added dataset link to CaseStudy{i}.md")
