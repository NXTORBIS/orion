"""Generate reasoning and logic problems for multi-step thinking"""

import random
import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class ReasoningProblem:
    id: str
    problem: str
    answer: str
    family: str
    level: int
    reasoning_type: str

def generate_logic_puzzle(seed: int, level: int = 2):
    """Logic puzzles requiring deduction"""
    random.seed(seed)

    if level == 1:
        problem = """
Alice is taller than Bob.
Bob is taller than Carol.
Is Carol taller than Alice?
"""
        answer = "No"
    elif level == 2:
        problem = """
All cats are animals.
Fluffy is a cat.
Is Fluffy an animal?
"""
        answer = "Yes"
    else:
        problem = """
There are 5 houses in a row.
House 1 is red. House 3 has a cat.
If the house with a dog is between the house with a cat and the house with a bird:
Where is the dog?
"""
        answer = "House 4 or the constraints need more specification"

    return ReasoningProblem(
        id=f"reason-logic-{seed}",
        problem=problem,
        answer=answer,
        family="logic_puzzle",
        level=level,
        reasoning_type="deduction"
    )

def generate_wordplay(seed: int, level: int = 2):
    """Analogies and word reasoning"""
    random.seed(seed)

    analogies = [
        ("Dog is to puppy as Cat is to", "kitten"),
        ("Hot is to cold as Light is to", "dark"),
        ("Book is to read as Food is to", "eat"),
        ("Wheel is to car as Blade is to", "fan/sword"),
        ("Brave is to timid as Happy is to", "sad"),
    ]

    if level <= 2:
        problem_text, answer = random.choice(analogies)
        problem = f"Complete the analogy: {problem_text}"
        answer = answer
    else:
        problem = "What is the opposite of 'beginning'?"
        answer = "end"

    return ReasoningProblem(
        id=f"reason-analogy-{seed}",
        problem=problem,
        answer=answer,
        family="analogy",
        level=level,
        reasoning_type="semantic"
    )

def generate_common_sense(seed: int, level: int = 2):
    """Common sense reasoning"""
    random.seed(seed)

    questions = [
        ("Can a penguin fly?", "No"),
        ("Do plants need water to grow?", "Yes"),
        ("Is ice hot or cold?", "Cold"),
        ("Can a car swim?", "No"),
        ("Do we sleep at night or during the day?", "At night"),
    ]

    if level <= 2:
        problem, answer = random.choice(questions)
    else:
        problem = "Why do we wear coats in winter?"
        answer = "To keep warm"

    return ReasoningProblem(
        id=f"reason-sense-{seed}",
        problem=problem,
        answer=answer,
        family="common_sense",
        level=level,
        reasoning_type="common_sense"
    )

def generate_causal_reasoning(seed: int, level: int = 2):
    """Cause and effect reasoning"""
    random.seed(seed)

    if level == 1:
        problem = "If it rains, the ground gets wet. It is raining. Is the ground wet?"
        answer = "Yes"
    elif level == 2:
        problem = """
Plants need sunlight to grow.
This plant is in a dark room.
Will this plant grow well?
"""
        answer = "No, not without sunlight"
    else:
        problem = """
Lack of sleep causes poor concentration.
Poor concentration causes mistakes.
Someone made many mistakes today.
Can we conclude they didn't sleep well?
"""
        answer = "Not necessarily - it's one possible cause but not the only one"

    return ReasoningProblem(
        id=f"reason-causal-{seed}",
        problem=problem,
        answer=answer,
        family="causal_reasoning",
        level=level,
        reasoning_type="causality"
    )

def generate_multistep_problem(seed: int, level: int = 2):
    """Multi-step reasoning problems"""
    random.seed(seed)

    if level == 1:
        problem = "John has 3 apples. He buys 2 more. He eats 1. How many does he have?"
        answer = "4"
    elif level == 2:
        problem = """
Alice starts with $100.
She spends 1/4 on a book.
She spends 1/2 of what's left on a movie.
How much money remains?
"""
        answer = "$37.50"
    else:
        problem = """
A train leaves city A at 60 mph.
Another train leaves city B (150 miles away) at 80 mph, heading toward A.
They travel toward each other.
When do they meet?
"""
        answer = "Approximately 57.7 minutes or 0.96 hours"

    return ReasoningProblem(
        id=f"reason-multistep-{seed}",
        problem=problem,
        answer=answer,
        family="multistep",
        level=level,
        reasoning_type="multistep"
    )

def generate_reasoning_dataset(output_path: str, n_per_family: int = 200):
    """Generate comprehensive reasoning training dataset"""
    random.seed(42)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    generators = [
        ("logic", generate_logic_puzzle, 2),
        ("analogy", generate_wordplay, 2),
        ("sense", generate_common_sense, 2),
        ("causal", generate_causal_reasoning, 2),
        ("multistep", generate_multistep_problem, 2),
    ]

    with open(output_path, "w") as f:
        for gen_name, gen_func, default_level in generators:
            for level in [1, 2, 3]:
                for i in range(n_per_family // 3):
                    try:
                        prob = gen_func(seed=i * 4000 + level * 100, level=level)
                        f.write(json.dumps(asdict(prob)) + "\n")
                    except:
                        pass

    print(f"Generated {n_per_family * len(generators)} reasoning problems to {output_path}")

if __name__ == "__main__":
    generate_reasoning_dataset("data/raw/synth_reasoning/train.jsonl", n_per_family=200)
    generate_reasoning_dataset("data/raw/synth_reasoning/test.jsonl", n_per_family=50)
