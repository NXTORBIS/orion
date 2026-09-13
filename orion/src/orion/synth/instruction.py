"""Generate instruction-following problems for ChatGPT-level compliance"""

import random
import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class InstructionProblem:
    id: str
    problem: str
    answer: str
    family: str
    level: int
    instruction_type: str

def generate_format_compliance(seed: int, level: int = 2):
    """Instruction format compliance (follow exact format requirements)"""
    random.seed(seed)

    formats = [
        ("Respond in JSON format", '{"response": "answer"}', "Follow JSON format"),
        ("Answer in exactly 1 sentence", "Complete answer in one sentence.", "Concise response"),
        ("Use bullet points", "• Point 1\n• Point 2\n• Point 3", "Bullet format"),
        ("Number your steps", "1. First step\n2. Second step\n3. Third step", "Numbered steps"),
        ("Start with 'Answer:'", "Answer: [content]", "Prefixed response"),
    ]

    problem_text, answer, family = random.choice(formats)
    problem = f"Explain Python lists. {problem_text}"

    return InstructionProblem(
        id=f"instr-format-{seed}",
        problem=problem,
        answer=answer,
        family=family,
        level=level,
        instruction_type="format_compliance"
    )

def generate_constraint_following(seed: int, level: int = 2):
    """Follow multiple constraints simultaneously"""
    random.seed(seed)

    if level == 1:
        problem = "Explain variables. Keep it under 50 words."
        answer = "Variables store data values with names for reuse."
    elif level == 2:
        problem = "Explain functions. Use exactly 3 examples. Keep each under 10 words."
        answer = "1. math.sqrt(16) computes square root.\n2. len([1,2,3]) returns list length.\n3. print('hi') displays text."
    else:
        problem = "Explain machine learning. No jargon. Use 2 analogies. Conclude with 1 limitation."
        answer = "Like learning from examples (student studies past tests). Pattern recognition (finding what works). Limitation: needs lots of data."

    return InstructionProblem(
        id=f"instr-constraint-{seed}",
        problem=problem,
        answer=answer,
        family="constraint_following",
        level=level,
        instruction_type="constraint_following"
    )

def generate_tone_adaptation(seed: int, level: int = 2):
    """Adapt tone and style to instructions"""
    random.seed(seed)

    if level == 1:
        problem = "Explain variables in a professional tone."
        answer = "Variables are fundamental programming constructs that store and manage data values."
    elif level == 2:
        problem = "Explain variables as if teaching a 5-year-old."
        answer = "A variable is like a box where you put things! You can give the box a name so you remember what's inside."
    else:
        problem = "Explain machine learning: formal academic style, then casual everyday language."
        answer = "FORMAL: Machine learning employs algorithmic approaches to discern patterns from empirical data. CASUAL: ML is basically teaching computers to recognize patterns by showing them lots of examples."

    return InstructionProblem(
        id=f"instr-tone-{seed}",
        problem=problem,
        answer=answer,
        family="tone_adaptation",
        level=level,
        instruction_type="tone_adaptation"
    )

def generate_boundary_cases(seed: int, level: int = 2):
    """Handle edge cases and boundary conditions"""
    random.seed(seed)

    if level == 1:
        problem = "What's 0 divided by 5?"
        answer = "0"
    elif level == 2:
        problem = "What happens when you divide by 0? Explain the error."
        answer = "Division by zero causes a ZeroDivisionError because it's mathematically undefined."
    else:
        problem = "Explain null/None in 3 contexts: database, programming, and statistics. What differs?"
        answer = "Database: NULL unknown value. Programming: None no object. Statistics: null hypothesis assumption. All mean 'absence' but differently."

    return InstructionProblem(
        id=f"instr-boundary-{seed}",
        problem=problem,
        answer=answer,
        family="boundary_cases",
        level=level,
        instruction_type="boundary_cases"
    )

def generate_multi_turn(seed: int, level: int = 2):
    """Multi-turn conversation consistency"""
    random.seed(seed)

    if level == 1:
        problem = "Q1: What is Python? Q2: Is it interpreted? (Be consistent)"
        answer = "Python is a programming language. Yes, Python is primarily interpreted."
    elif level == 2:
        problem = "User says 'Teach me recursion'. You: explain + example. User: 'How deep can it go?'. You: answer + limitation. (Stay consistent)"
        answer = "Recursion is when function calls itself. Example: factorial(5) = 5*factorial(4). Depth limited by call stack, typically ~1000 levels."
    else:
        problem = "3-turn: explain ML, critique explanation, improve it. Maintain coherent narrative."
        answer = "Turn1: ML learns patterns from data. Turn2: Too vague, needs types. Turn3: Supervised learns labels, unsupervised finds structure, reinforcement learns rewards."

    return InstructionProblem(
        id=f"instr-multiturn-{seed}",
        problem=problem,
        answer=answer,
        family="multi_turn",
        level=level,
        instruction_type="multi_turn"
    )

def generate_instruction_dataset(output_path: str, n_per_family: int = 300):
    """Generate instruction-following training dataset"""
    random.seed(42)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    generators = [
        ("format", generate_format_compliance, 2),
        ("constraint", generate_constraint_following, 2),
        ("tone", generate_tone_adaptation, 2),
        ("boundary", generate_boundary_cases, 2),
        ("multiturn", generate_multi_turn, 2),
    ]

    with open(output_path, "w") as f:
        for gen_name, gen_func, default_level in generators:
            for level in [1, 2, 3]:
                for i in range(n_per_family // 3):
                    try:
                        prob = gen_func(seed=i * 6000 + level * 100, level=level)
                        f.write(json.dumps(asdict(prob)) + "\n")
                    except:
                        pass

    print(f"Generated {n_per_family * len(generators)} instruction problems to {output_path}")

if __name__ == "__main__":
    generate_instruction_dataset("data/raw/synth_instruction/train.jsonl", n_per_family=300)
    generate_instruction_dataset("data/raw/synth_instruction/test.jsonl", n_per_family=75)
