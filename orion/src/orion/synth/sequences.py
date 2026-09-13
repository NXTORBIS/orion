"""Generate sequence problems targeting identified weakness (0% baseline accuracy)"""

import random
from dataclasses import dataclass, asdict

@dataclass
class SequenceProblem:
    id: str
    problem: str
    answer: str
    family: str
    level: int

def generate_arithmetic_sequence(seed: int, level: int = 1):
    random.seed(seed)
    start = random.randint(1, 20)
    diff = random.randint(1, 10)
    pos = random.randint(5, 15)
    answer = start + (pos - 1) * diff

    seq_str = ", ".join(str(start + i * diff) for i in range(5))
    problem = f"Arithmetic sequence: {seq_str}, ... What is the {pos}th term?"

    return SequenceProblem(
        id=f"seq-arithmetic-{seed}",
        problem=problem,
        answer=str(answer),
        family="arithmetic_sequence",
        level=level
    )

def generate_geometric_sequence(seed: int, level: int = 2):
    random.seed(seed)
    start = random.randint(1, 10)
    ratio = random.randint(2, 5)
    pos = random.randint(4, 8)
    answer = start * (ratio ** (pos - 1))

    seq_str = ", ".join(str(start * (ratio ** i)) for i in range(4))
    problem = f"Geometric sequence: {seq_str}, ... What is the {pos}th term?"

    return SequenceProblem(
        id=f"seq-geometric-{seed}",
        problem=problem,
        answer=str(answer),
        family="geometric_sequence",
        level=level
    )

def generate_fibonacci_variant(seed: int, level: int = 2):
    random.seed(seed)
    a, b = random.randint(1, 5), random.randint(1, 5)
    terms = [a, b]
    for _ in range(8):
        terms.append(terms[-1] + terms[-2])
    pos = random.randint(6, 10)
    answer = terms[pos - 1]

    seq_str = ", ".join(str(t) for t in terms[:5])
    problem = f"Sequence: {seq_str}, ... What is the {pos}th term? (Each term is sum of previous two)"

    return SequenceProblem(
        id=f"seq-fibonacci-{seed}",
        problem=problem,
        answer=str(answer),
        family="fibonacci_variant",
        level=level
    )

def generate_polynomial_sequence(seed: int, level: int = 3):
    random.seed(seed)
    a, b, c = random.randint(1, 3), random.randint(2, 5), random.randint(0, 3)
    pos = random.randint(6, 10)
    answer = a * pos * pos + b * pos + c

    seq_vals = [a * i * i + b * i + c for i in range(1, 6)]
    seq_str = ", ".join(str(v) for v in seq_vals)
    problem = f"Sequence: {seq_str}, ... What is the {pos}th term?"

    return SequenceProblem(
        id=f"seq-polynomial-{seed}",
        problem=problem,
        answer=str(answer),
        family="polynomial_sequence",
        level=level
    )

def generate_sequence_dataset(output_path: str, n_per_family: int = 200):
    """Generate sequence training dataset"""
    import json
    from pathlib import Path

    random.seed(42)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    generators = [
        ("arithmetic", generate_arithmetic_sequence, 1),
        ("geometric", generate_geometric_sequence, 2),
        ("fibonacci", generate_fibonacci_variant, 2),
        ("polynomial", generate_polynomial_sequence, 3),
    ]

    with open(output_path, "w") as f:
        for gen_name, gen_func, default_level in generators:
            for i in range(n_per_family):
                # Mix of difficulty levels
                level = default_level if i % 3 != 0 else default_level + 1
                prob = gen_func(seed=i * 1000, level=level)
                f.write(json.dumps(asdict(prob)) + "\n")

    print(f"Generated {n_per_family * len(generators)} sequence problems to {output_path}")

if __name__ == "__main__":
    generate_sequence_dataset("data/raw/synth_sequences/train.jsonl", n_per_family=200)
    generate_sequence_dataset("data/raw/synth_sequences/test.jsonl", n_per_family=50)
