"""Generate general knowledge problems across history, geography, culture"""

import random
import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class KnowledgeProblem:
    id: str
    problem: str
    answer: str
    family: str
    level: int
    domain: str

def generate_history_question(seed: int, level: int = 2):
    """History and historical events"""
    random.seed(seed)

    history_qa = [
        ("What year did World War II end?", "1945"),
        ("Who was the first President of the United States?", "George Washington"),
        ("In what year did the Titanic sink?", "1912"),
        ("Who wrote the Declaration of Independence?", "Thomas Jefferson"),
        ("What ancient civilization built the pyramids?", "Egyptian"),
    ]

    if level <= 2:
        problem, answer = random.choice(history_qa)
    else:
        problem = "What were the major causes of the French Revolution?"
        answer = "Economic crisis, food shortages, Enlightenment ideas, inequality"

    return KnowledgeProblem(
        id=f"know-hist-{seed}",
        problem=problem,
        answer=answer,
        family="history",
        level=level,
        domain="history"
    )

def generate_geography_question(seed: int, level: int = 2):
    """Geography, capitals, locations"""
    random.seed(seed)

    geography_qa = [
        ("What is the capital of France?", "Paris"),
        ("What is the largest ocean on Earth?", "Pacific"),
        ("What continent is Australia on?", "Oceania or Australia (continent)"),
        ("What is the longest river in the world?", "Nile"),
        ("How many continents are there?", "7"),
    ]

    if level <= 2:
        problem, answer = random.choice(geography_qa)
    else:
        problem = "Which countries border the Mediterranean Sea?"
        answer = "Spain, Italy, Greece, Turkey, Syria, Lebanon, Israel, Egypt, Libya, Tunisia, Algeria, Morocco"

    return KnowledgeProblem(
        id=f"know-geo-{seed}",
        problem=problem,
        answer=answer,
        family="geography",
        level=level,
        domain="geography"
    )

def generate_culture_question(seed: int, level: int = 2):
    """Culture, arts, literature"""
    random.seed(seed)

    culture_qa = [
        ("Who wrote 'Romeo and Juliet'?", "William Shakespeare"),
        ("What artist painted the Mona Lisa?", "Leonardo da Vinci"),
        ("What is the most spoken language in the world?", "Mandarin Chinese"),
        ("In what country did the Olympics originate?", "Greece"),
        ("What musical instrument has 88 keys?", "Piano"),
    ]

    if level <= 2:
        problem, answer = random.choice(culture_qa)
    else:
        problem = "Describe the Renaissance period and its significance"
        answer = "14th-17th century cultural movement emphasizing humanism, art, and learning"

    return KnowledgeProblem(
        id=f"know-cult-{seed}",
        problem=problem,
        answer=answer,
        family="culture",
        level=level,
        domain="culture"
    )

def generate_science_fact(seed: int, level: int = 2):
    """Science facts and natural world"""
    random.seed(seed)

    science_qa = [
        ("What is the chemical symbol for gold?", "Au"),
        ("How many bones are in the human body?", "206"),
        ("What is the speed of light?", "3 x 10^8 m/s or 300,000 km/s"),
        ("What gas do plants absorb from the atmosphere?", "Carbon dioxide (CO2)"),
        ("What is the smallest unit of life?", "Cell"),
    ]

    if level <= 2:
        problem, answer = random.choice(science_qa)
    else:
        problem = "Explain photosynthesis and its importance"
        answer = "Process where plants convert sunlight to chemical energy (glucose), producing oxygen"

    return KnowledgeProblem(
        id=f"know-sci-{seed}",
        problem=problem,
        answer=answer,
        family="science_facts",
        level=level,
        domain="science"
    )

def generate_technology_question(seed: int, level: int = 2):
    """Modern technology and computing"""
    random.seed(seed)

    tech_qa = [
        ("What does HTML stand for?", "HyperText Markup Language"),
        ("Who invented the World Wide Web?", "Tim Berners-Lee"),
        ("What year was the internet made public?", "1991"),
        ("What is the most popular programming language for web development?", "JavaScript"),
        ("What does CPU stand for?", "Central Processing Unit"),
    ]

    if level <= 2:
        problem, answer = random.choice(tech_qa)
    else:
        problem = "Explain the difference between machine learning and deep learning"
        answer = "ML is broader; DL is subset using neural networks with multiple layers"

    return KnowledgeProblem(
        id=f"know-tech-{seed}",
        problem=problem,
        answer=answer,
        family="technology",
        level=level,
        domain="technology"
    )

def generate_knowledge_dataset(output_path: str, n_per_family: int = 200):
    """Generate comprehensive knowledge training dataset"""
    random.seed(42)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    generators = [
        ("history", generate_history_question, 2),
        ("geography", generate_geography_question, 2),
        ("culture", generate_culture_question, 2),
        ("science", generate_science_fact, 2),
        ("technology", generate_technology_question, 2),
    ]

    with open(output_path, "w") as f:
        for gen_name, gen_func, default_level in generators:
            for level in [1, 2, 3]:
                for i in range(n_per_family // 3):
                    try:
                        prob = gen_func(seed=i * 5000 + level * 100, level=level)
                        f.write(json.dumps(asdict(prob)) + "\n")
                    except:
                        pass

    print(f"Generated {n_per_family * len(generators)} knowledge problems to {output_path}")

if __name__ == "__main__":
    generate_knowledge_dataset("data/raw/synth_knowledge/train.jsonl", n_per_family=200)
    generate_knowledge_dataset("data/raw/synth_knowledge/test.jsonl", n_per_family=50)
