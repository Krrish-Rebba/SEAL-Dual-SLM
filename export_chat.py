import json
import os

transcript_path = r"C:\Users\Krrish Rebba\.gemini\antigravity-ide\brain\3f68e9e9-a079-46b4-afec-76b08ff902c9\.system_generated\logs\transcript.jsonl"
export_path = r"C:\Users\Krrish Rebba\OneDrive\ドキュメント\RM\Chat_Export.md"

if not os.path.exists(transcript_path):
    print("Transcript not found.")
else:
    with open(export_path, "w", encoding="utf-8") as out:
        out.write("# Antigravity Agent Chat Export\n\n")
        out.write("This document is a complete log of the conversation related to the Dual-SLM continuous learning architecture.\n\n")
        out.write("---\n\n")
        
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    step = json.loads(line)
                    step_type = step.get("type", "")
                    content = step.get("content", "")
                    
                    if not content:
                        continue
                        
                    if step_type == "USER_INPUT":
                        out.write(f"### 👤 User:\n{content}\n\n---\n\n")
                    elif step_type == "PLANNER_RESPONSE":
                        out.write(f"### 🤖 Agent:\n{content}\n\n---\n\n")
                        
                except json.JSONDecodeError:
                    continue
                    
    print(f"Chat successfully exported to {export_path}")
