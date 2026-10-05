import os

target_dir = r"C:\Users\Krrish Rebba\OneDrive\ドキュメント\RM\Findings"
link_text = "\n\n> [!NOTE]\n> For a full breakdown of the raw Teacher Prompts, Student Inputs, and Model Outputs used in this test, refer to the [Master Data Log](file:///C:/Users/Krrish%20Rebba/OneDrive/ドキュメント/RM/Findings/Data_Log_Master.md).\n"

for i in range(1, 14):
    file_path = os.path.join(target_dir, f"CaseStudy{i}.md")
    if os.path.exists(file_path):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(link_text)
        print(f"Appended link to CaseStudy{i}.md")
