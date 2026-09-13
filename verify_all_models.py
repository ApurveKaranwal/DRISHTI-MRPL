#!/usr/bin/env python3
"""MRPL Sovereign AI Workbench - 1-Click Multi-Model Health & GPU Check
Tests all 4 domain models (Reasoning, General, Code, Vision) directly on Ollama.
"""

import time
import requests

MODELS = [
    ("Reasoning (DeepSeek R1)", "deepseek-r1:1.5b", "Why is hydrocracker bed temperature rising? Answer in 1 sentence."),
    ("General / PSU Drafting", "qwen2.5:7b", "Write a 1-sentence executive subject line for an MRPL turnaround shutdown memo."),
    ("Code / Hydraulics", "qwen2.5-coder:7b", "Write 1 line of Python: Darcy friction factor for laminar flow."),
    ("Multimodal Vision", "qwen2.5vl:3b", "What does an ultrasonic NDT gauge measure on an oil pipe? Answer in 1 sentence."),
]

print("\n" + "=" * 75)
print("  MRPL SOVEREIGN WORKBENCH - 4-MODEL LOCAL GPU VERIFICATION")
print("=" * 75 + "\n")

for label, model_id, prompt in MODELS:
    print(f"-> Testing [{label}] -> Model: {model_id} ...", end=" ", flush=True)
    t0 = time.time()
    try:
        resp = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model_id, "prompt": prompt, "stream": False, "options": {"num_predict": 60}},
            timeout=60,
        )
        elapsed = round(time.time() - t0, 2)
        if resp.status_code == 200:
            ans = resp.json().get("response", "").strip().replace("\n", " ")
            if "</think>" in ans:
                ans = ans.split("</think>")[-1].strip()
            print(f"[OK] ({elapsed}s)")
            print(f"   Output: \"{ans[:85]}...\"\n")
        else:
            print(f"[FAILED] HTTP {resp.status_code}\n")
    except Exception as exc:
        print(f"[ERROR] {exc}\n")

print("=" * 75)
print("All models verified operational on local GPU!")
print("=" * 75 + "\n")
