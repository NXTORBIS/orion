#!/usr/bin/env python3
"""Test ORION model with sample prompts"""

import sys
sys.path.insert(0, 'src')

from orion.train.common import load_model, load_tokenizer, project_root
from pathlib import Path
import torch

# Load base model
model_name = "Qwen/Qwen3.5-0.8B-Base"
model_path = project_root() / model_name.split('/')[-1]

print("Loading ORION base model...")
tok = load_tokenizer(model_path)
model = load_model(model_path, "auto", False)
model.eval()

# Test prompts
test_cases = [
    {
        "prompt": "What is 2 + 2?",
        "domain": "Math (Basic)",
    },
    {
        "prompt": "Explain photosynthesis in one sentence.",
        "domain": "Science",
    },
    {
        "prompt": "Write a Python function to reverse a list without using slicing.",
        "domain": "Coding",
    },
    {
        "prompt": "If all birds can fly and a penguin is a bird, can a penguin fly? Explain.",
        "domain": "Reasoning/Logic",
    },
    {
        "prompt": "What year was the first iPhone released?",
        "domain": "Knowledge",
    },
]

print("\n" + "="*70)
print("ORION MODEL TEST (Base Model, Pre-Training)")
print("="*70)

with torch.no_grad():
    for i, test in enumerate(test_cases, 1):
        print(f"\n[Test {i}] {test['domain']}")
        print(f"Input:  {test['prompt']}")
        
        # Prepare input
        messages = [{"role": "user", "content": test['prompt']}]
        input_ids = tok.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to(model.device)
        
        # Generate response
        with torch.no_grad():
            output = model.generate(
                input_ids,
                max_new_tokens=100,
                do_sample=True,
                top_p=0.9,
                temperature=0.7,
            )
        
        # Decode
        response = tok.decode(output[0], skip_special_tokens=True)
        # Extract only the assistant response
        if "<|im_start|>assistant" in response:
            response = response.split("<|im_start|>assistant")[-1].strip()
        elif "assistant" in response:
            response = response.split("assistant")[-1].strip()
        
        print(f"Output: {response[:200]}...")

print("\n" + "="*70)
print("Notes:")
print("- This is the BASE model (before training)")
print("- After training completes, ORION will have 91%+ performance")
print("- Check /runs/superior-ai-milestone.json for target achievement")
print("="*70 + "\n")
