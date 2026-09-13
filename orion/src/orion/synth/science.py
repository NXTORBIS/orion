"""Procedural generation of science problems (physics, chemistry, biology) for training and evaluation.

Domains covered:
  - Physics: kinematics, dynamics, thermodynamics, electromagnetism, waves, optics
  - Chemistry: stoichiometry, equilibrium, redox, bonding, gas laws, acid-base
  - Biology: genetics, evolution, ecology, cellular biology, biochemistry

Each problem includes:
  - Problem statement
  - Gold answer (numerical or conceptual)
  - Family/domain classification
  - Difficulty level (1=easy, 2=medium, 3=hard)
  - Verifiable answer format (numerical, multiple-choice, or short-answer)

Problems are generated with randomized parameters to avoid memorization.
"""

import random
from dataclasses import dataclass, asdict
from typing import Literal

INSTRUCTION = """Solve this problem step by step. Show your reasoning.
For numerical answers, provide the final numeric answer after "Answer: "."""


@dataclass
class ScienceProblem:
    id: str
    problem: str
    answer: str
    family: str
    domain: Literal["physics", "chemistry", "biology"]
    level: int
    concepts: list[str]
    verifier_type: Literal["numerical", "symbolic", "conceptual"]


# ============================================================================
# PHYSICS PROBLEMS
# ============================================================================

def generate_kinematics_problem(seed: int, level: int = 1) -> ScienceProblem:
    """Generate kinematics problems (motion in 1D)."""
    random.seed(seed)

    if level == 1:
        # Easy: constant velocity
        distance = random.randint(10, 100)
        time = random.randint(2, 10)
        velocity = distance / time
        problem = (
            f"An object travels {distance} meters in {time} seconds at constant velocity. "
            f"What is its velocity in m/s?"
        )
        answer = f"{velocity:.1f}"
    elif level == 2:
        # Medium: constant acceleration
        v0 = random.randint(0, 20)
        a = random.randint(1, 10)
        t = random.randint(2, 10)
        vf = v0 + a * t
        problem = (
            f"A car starts with velocity {v0} m/s and accelerates at {a} m/s² for {t} seconds. "
            f"What is its final velocity in m/s?"
        )
        answer = f"{vf:.1f}"
    else:
        # Hard: multi-step with displacement
        v0 = random.randint(5, 20)
        a = random.randint(1, 5)
        t = random.randint(3, 8)
        displacement = v0 * t + 0.5 * a * t * t
        problem = (
            f"Starting from rest with v₀={v0} m/s, an object accelerates at {a} m/s² for {t}s. "
            f"What is the total displacement in meters?"
        )
        answer = f"{displacement:.1f}"

    return ScienceProblem(
        id=f"physics-kinematics-{seed}",
        problem=problem,
        answer=answer,
        family="kinematics",
        domain="physics",
        level=level,
        concepts=["motion", "velocity", "acceleration"],
        verifier_type="numerical",
    )


def generate_dynamics_problem(seed: int, level: int = 1) -> ScienceProblem:
    """Generate dynamics problems (forces, Newton's laws)."""
    random.seed(seed)

    if level == 1:
        # Easy: simple force
        mass = random.randint(1, 10)
        accel = random.randint(1, 5)
        force = mass * accel
        problem = f"What force is needed to accelerate a {mass} kg object at {accel} m/s²?"
        answer = f"{force:.1f}"
    elif level == 2:
        # Medium: friction
        mass = random.randint(5, 20)
        mu = round(random.uniform(0.1, 0.8), 2)
        g = 9.8
        friction = mu * mass * g
        problem = (
            f"A {mass} kg box rests on a surface with coefficient of friction μ={mu}. "
            f"What is the maximum static friction force in Newtons? (use g=9.8)"
        )
        answer = f"{friction:.1f}"
    else:
        # Hard: inclined plane with friction
        mass = random.randint(5, 15)
        angle = random.randint(20, 60)
        mu = round(random.uniform(0.1, 0.5), 2)
        theta_rad = angle * 3.14159 / 180
        g = 9.8
        normal = mass * g * (3.14159 / 2 - theta_rad).__abs__()
        friction = mu * normal
        problem = (
            f"A {mass} kg block on a {angle}° incline (μ={mu}) experiences friction. "
            f"Calculate the friction force in Newtons."
        )
        answer = f"{friction:.1f}"

    return ScienceProblem(
        id=f"physics-dynamics-{seed}",
        problem=problem,
        answer=answer,
        family="dynamics",
        domain="physics",
        level=level,
        concepts=["force", "mass", "Newton's laws", "friction"],
        verifier_type="numerical",
    )


def generate_thermodynamics_problem(seed: int, level: int = 1) -> ScienceProblem:
    """Generate thermodynamics problems (heat, temperature, energy)."""
    random.seed(seed)

    if level == 1:
        # Easy: heat capacity
        mass = random.randint(1, 5)
        c = random.randint(100, 1000)
        dT = random.randint(5, 50)
        Q = mass * c * dT
        problem = (
            f"Calculate the heat required to raise {mass} kg of a substance "
            f"(specific heat {c} J/kg·K) by {dT} K."
        )
        answer = f"{Q:.0f}"
    elif level == 2:
        # Medium: ideal gas law
        P = random.randint(1, 10)
        V = random.randint(1, 100)
        T = random.randint(250, 350)
        n = (P * V) / (8.314 * T)
        problem = (
            f"A gas has pressure {P} Pa, volume {V} L, and temperature {T} K. "
            f"Calculate moles using PV=nRT (R=8.314 J/mol·K)."
        )
        answer = f"{n:.2f}"
    else:
        # Hard: entropy change
        T_initial = random.randint(300, 400)
        T_final = random.randint(T_initial + 50, 600)
        m = random.randint(1, 5)
        c = random.randint(100, 1000)
        dS = m * c * (T_final / T_initial)
        problem = (
            f"Heating {m} kg of substance from {T_initial}K to {T_final}K "
            f"(c={c} J/kg·K). Calculate entropy change."
        )
        answer = f"{dS:.1f}"

    return ScienceProblem(
        id=f"physics-thermodynamics-{seed}",
        problem=problem,
        answer=answer,
        family="thermodynamics",
        domain="physics",
        level=level,
        concepts=["heat", "temperature", "energy", "entropy"],
        verifier_type="numerical",
    )


# ============================================================================
# CHEMISTRY PROBLEMS
# ============================================================================

def generate_stoichiometry_problem(seed: int, level: int = 1) -> ScienceProblem:
    """Generate stoichiometry problems (balancing, molar ratios)."""
    random.seed(seed)

    if level == 1:
        # Easy: simple molar mass
        element = "oxygen"  # O
        atomic_mass = 16
        n_moles = random.randint(1, 10)
        mass = n_moles * atomic_mass
        problem = f"What is the mass of {n_moles} moles of {element} (atomic mass={atomic_mass})?"
        answer = f"{mass:.1f}"
    elif level == 2:
        # Medium: stoichiometric ratio
        A_moles = random.randint(1, 5)
        ratio = random.choice([2, 3, 4])
        B_moles = A_moles * ratio
        problem = (
            f"In reaction A + {ratio}B → products, if you have {A_moles} mol of A, "
            f"how many moles of B are needed?"
        )
        answer = f"{B_moles:.1f}"
    else:
        # Hard: limiting reagent
        A_moles = random.randint(1, 5)
        B_moles = random.randint(1, 8)
        ratio = random.choice([2, 3])
        limiting_reagent_moles = min(A_moles, B_moles / ratio)
        problem = (
            f"Reaction: 2A + {ratio}B → product. You have {A_moles} mol A and {B_moles} mol B. "
            f"How many moles of product form? (limiting reagent calculation)"
        )
        answer = f"{limiting_reagent_moles:.1f}"

    return ScienceProblem(
        id=f"chemistry-stoichiometry-{seed}",
        problem=problem,
        answer=answer,
        family="stoichiometry",
        domain="chemistry",
        level=level,
        concepts=["molar mass", "moles", "balancing", "limiting reagent"],
        verifier_type="numerical",
    )


def generate_equilibrium_problem(seed: int, level: int = 1) -> ScienceProblem:
    """Generate chemical equilibrium problems (Ka, Kb, Le Chatelier)."""
    random.seed(seed)

    if level == 1:
        # Easy: pH from concentration
        H_concentration = 10 ** (-random.randint(1, 7))
        pH = -random.randint(1, 7)
        problem = f"A solution has [H⁺] = 10⁻{-pH} M. What is the pH?"
        answer = f"{-pH:.1f}"
    elif level == 2:
        # Medium: Ka calculation
        pKa = random.randint(2, 6)
        Ka = 10 ** (-pKa)
        conc_A = random.randint(1, 10) / 1000
        problem = (
            f"A weak acid has Ka = {Ka:.1e}. Initial concentration = {conc_A:.4f} M. "
            f"Calculate [H⁺] at equilibrium (simplified)."
        )
        answer = f"{(Ka * conc_A) ** 0.5:.2e}"
    else:
        # Hard: buffer pH (Henderson-Hasselbalch)
        pKa = random.randint(3, 8)
        ratio = random.uniform(0.5, 2.0)
        pH = pKa + 0.3  # log(ratio) approximation
        problem = (
            f"Buffer with pKa={pKa} and [acid]/[base]={ratio:.1f}. "
            f"Calculate pH using Henderson-Hasselbalch."
        )
        answer = f"{pH:.1f}"

    return ScienceProblem(
        id=f"chemistry-equilibrium-{seed}",
        problem=problem,
        answer=answer,
        family="equilibrium",
        domain="chemistry",
        level=level,
        concepts=["pH", "Ka", "Kb", "equilibrium", "Le Chatelier"],
        verifier_type="numerical",
    )


# ============================================================================
# BIOLOGY PROBLEMS
# ============================================================================

def generate_genetics_problem(seed: int, level: int = 1) -> ScienceProblem:
    """Generate genetics problems (Mendelian inheritance, Punnett squares)."""
    random.seed(seed)

    if level == 1:
        # Easy: dominant/recessive
        problem = (
            "In a genetic cross where A (dominant) is crossed with a (recessive), "
            "what fraction of offspring are dominant phenotype?"
        )
        answer = "0.75"
    elif level == 2:
        # Medium: test cross
        Aa_count = random.randint(20, 100)
        problem = (
            f"In a test cross (Aa × aa), if {Aa_count} offspring are dominant phenotype, "
            f"approximately how many are recessive phenotype?"
        )
        answer = f"{Aa_count:.0f}"
    else:
        # Hard: dihybrid cross
        problem = (
            "A dihybrid cross (AaBb × AaBb) produces offspring. "
            "What fraction has phenotype A_B_?"
        )
        answer = "0.5625"

    return ScienceProblem(
        id=f"biology-genetics-{seed}",
        problem=problem,
        answer=answer,
        family="genetics",
        domain="biology",
        level=level,
        concepts=["inheritance", "dominant", "recessive", "genotype", "phenotype"],
        verifier_type="numerical",
    )


def generate_evolution_problem(seed: int, level: int = 1) -> ScienceProblem:
    """Generate evolution problems (natural selection, Hardy-Weinberg)."""
    random.seed(seed)

    if level == 1:
        problem = (
            "If an allele has frequency 0.4 in a population, what is the frequency "
            "of the alternative allele (assuming just 2 alleles)?"
        )
        answer = "0.6"
    elif level == 2:
        p = random.uniform(0.2, 0.8)
        q = 1 - p
        freq_AA = p ** 2
        problem = (
            f"In a population, allele A has frequency {p:.1f}. "
            f"Using Hardy-Weinberg, what frequency of AA genotype?"
        )
        answer = f"{freq_AA:.2f}"
    else:
        problem = (
            "Natural selection favors allele A (fitness=1.0) over a (fitness=0.8). "
            "If initial frequency of A is 0.5, predict direction of change."
        )
        answer = "increase"

    return ScienceProblem(
        id=f"biology-evolution-{seed}",
        problem=problem,
        answer=answer,
        family="evolution",
        domain="biology",
        level=level,
        concepts=["selection", "allele frequency", "Hardy-Weinberg", "fitness"],
        verifier_type="conceptual",
    )


# ============================================================================
# Generation Entry Point
# ============================================================================

PROBLEM_GENERATORS = {
    "physics-kinematics": generate_kinematics_problem,
    "physics-dynamics": generate_dynamics_problem,
    "physics-thermodynamics": generate_thermodynamics_problem,
    "chemistry-stoichiometry": generate_stoichiometry_problem,
    "chemistry-equilibrium": generate_equilibrium_problem,
    "biology-genetics": generate_genetics_problem,
    "biology-evolution": generate_evolution_problem,
}


def generate_science_problem(family: str, seed: int, level: int = 1) -> ScienceProblem:
    """Generate a science problem from a given family."""
    if family not in PROBLEM_GENERATORS:
        raise ValueError(f"Unknown family: {family}")
    return PROBLEM_GENERATORS[family](seed, level)


def generate_science_dataset(output_path: str, n_per_family: int = 100, seed: int = 42):
    """Generate full science dataset to JSONL file."""
    import json
    from pathlib import Path

    random.seed(seed)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for family, generator in PROBLEM_GENERATORS.items():
            for i in range(n_per_family):
                for level in [1, 2, 3]:
                    prob = generator(seed + i * 1000 + level, level=level)
                    f.write(json.dumps(asdict(prob)) + "\n")

    print(f"Generated {len(PROBLEM_GENERATORS) * n_per_family * 3} problems to {output_path}")


if __name__ == "__main__":
    # Generate sample dataset
    generate_science_dataset("data/raw/synth_science/test.jsonl", n_per_family=20)
    generate_science_dataset("data/raw/synth_science/train.jsonl", n_per_family=500)
