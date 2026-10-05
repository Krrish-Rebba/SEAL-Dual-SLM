import os

target_dir = r"C:\Users\Krrish Rebba\OneDrive\ドキュメント\RM\Findings"

banner = """
> [!WARNING]
> **SUPERSEDED EVALUATION LOGIC**
> The initial perplexity scores in the "Results" section below were generated using a deprecated, lightweight evaluator (using nats instead of bits, and lacking prompt masking). They have been **SUPERSEDED** by the "Empirical Audit Update & Re-Evaluation" section at the bottom of this document, which contains the true, mathematically verified execution scores. Do not use the original numbers for direct comparison.

"""

# We only need this on CS 2 through 9 (since 10 was fixed above, 11 was updated, 12 is meta, 13 is new)
for i in range(1, 10):
    file_path = os.path.join(target_dir, f"CaseStudy{i}.md")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            
        if "SUPERSEDED EVALUATION LOGIC" not in content:
            # Insert right after ## Results
            if "## Results" in content:
                content = content.replace("## Results", "## Results\n" + banner)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Added SUPERSEDED banner to CaseStudy{i}.md")
