"""Generate systems of equations problems targeting identified weakness (0% baseline accuracy)"""

import random
from dataclasses import dataclass, asdict

@dataclass
class SystemProblem:
    id: str
    problem: str
    answer: str
    family: str
    level: int

def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

def solve_2x2(a1, b1, c1, a2, b2, c2):
    """Solve system: a1*x + b1*y = c1, a2*x + b2*y = c2"""
    det = a1 * b2 - a2 * b1
    if det == 0:
        return None
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    if x == int(x) and y == int(y):
        return int(x), int(y)
    return x, y

def generate_2x2_substitution(seed: int, level: int = 2):
    """Simple 2x2 system solvable by substitution"""
    random.seed(seed)
    x = random.randint(-10, 10)
    y = random.randint(-10, 10)
    a1 = random.randint(1, 3)
    b1 = random.randint(1, 3)
    c1 = a1 * x + b1 * y
    a2 = random.randint(1, 2)
    b2 = random.randint(1, 2)
    c2 = a2 * x + b2 * y

    problem = f"Solve the system:\n{a1}x + {b1}y = {c1}\n{a2}x + {b2}y = {c2}"
    answer = f"x={x}, y={y}"

    return SystemProblem(
        id=f"sys-2x2-sub-{seed}",
        problem=problem,
        answer=answer,
        family="2x2_substitution",
        level=level
    )

def generate_2x2_elimination(seed: int, level: int = 2):
    """2x2 system requiring elimination method"""
    random.seed(seed)
    x = random.randint(-10, 10)
    y = random.randint(-10, 10)

    # Create coefficients that benefit from elimination
    a1, b1 = random.randint(2, 5), random.randint(2, 5)
    c1 = a1 * x + b1 * y

    # Second equation: make coefficients align for elimination
    mult = random.randint(1, 3)
    a2, b2 = a1 * mult, b1 * random.randint(1, 3)
    c2 = a2 * x + b2 * y

    problem = f"Solve the system:\n{a1}x + {b1}y = {c1}\n{a2}x + {b2}y = {c2}"
    answer = f"x={x}, y={y}"

    return SystemProblem(
        id=f"sys-2x2-elim-{seed}",
        problem=problem,
        answer=answer,
        family="2x2_elimination",
        level=level
    )

def generate_3x3_simple(seed: int, level: int = 3):
    """Simple 3x3 system with unique solution"""
    random.seed(seed)
    x = random.randint(-5, 5)
    y = random.randint(-5, 5)
    z = random.randint(-5, 5)

    # Diagonal-dominant system
    eq1_coeffs = [random.randint(3, 8), 1, 0]
    eq2_coeffs = [1, random.randint(3, 8), 1]
    eq3_coeffs = [0, 1, random.randint(3, 8)]

    c1 = eq1_coeffs[0] * x + eq1_coeffs[1] * y + eq1_coeffs[2] * z
    c2 = eq2_coeffs[0] * x + eq2_coeffs[1] * y + eq2_coeffs[2] * z
    c3 = eq3_coeffs[0] * x + eq3_coeffs[1] * y + eq3_coeffs[2] * z

    problem = (
        f"Solve the system:\n"
        f"{eq1_coeffs[0]}x + {eq1_coeffs[1]}y + {eq1_coeffs[2]}z = {c1}\n"
        f"{eq2_coeffs[0]}x + {eq2_coeffs[1]}y + {eq2_coeffs[2]}z = {c2}\n"
        f"{eq3_coeffs[0]}x + {eq3_coeffs[1]}y + {eq3_coeffs[2]}z = {c3}"
    )
    answer = f"x={x}, y={y}, z={z}"

    return SystemProblem(
        id=f"sys-3x3-simple-{seed}",
        problem=problem,
        answer=answer,
        family="3x3_simple",
        level=level
    )

def generate_system_dataset(output_path: str, n_per_family: int = 200):
    """Generate systems of equations training dataset"""
    import json
    from pathlib import Path

    random.seed(42)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    generators = [
        ("2x2_sub", generate_2x2_substitution, 2),
        ("2x2_elim", generate_2x2_elimination, 2),
        ("3x3_simple", generate_3x3_simple, 3),
    ]

    with open(output_path, "w") as f:
        for gen_name, gen_func, default_level in generators:
            for i in range(n_per_family):
                level = default_level
                prob = gen_func(seed=i * 2000, level=level)
                f.write(json.dumps(asdict(prob)) + "\n")

    print(f"Generated {n_per_family * len(generators)} system problems to {output_path}")

if __name__ == "__main__":
    generate_system_dataset("data/raw/synth_systems/train.jsonl", n_per_family=200)
    generate_system_dataset("data/raw/synth_systems/test.jsonl", n_per_family=50)
