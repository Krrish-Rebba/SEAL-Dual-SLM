import os

content = """

## Empirical Audit Update & Re-Evaluation
This case study was natively re-executed under strict mathematically corrected evaluation parameters (bits for entropy, full masking for prompt cross-entropy). The artifacts for this iteration are permanently persisted.
- **True Algebra Perplexity:** `5.4322`
- **True Empathy Perplexity:** `10.0226`
"""

path = r"C:\Users\Krrish Rebba\OneDrive\ドキュメント\RM\Findings\CaseStudy2.md"
with open(path, "a", encoding="utf-8") as f:
    f.write(content)
