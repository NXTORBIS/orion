"""Generate coding problems targeting algorithm understanding and debugging"""

import random
import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class CodingProblem:
    id: str
    problem: str
    answer: str
    family: str
    level: int
    category: str

def generate_array_manipulation(seed: int, level: int = 2):
    """Array/list manipulation problems"""
    random.seed(seed)
    n = random.randint(3, 10)
    arr = [random.randint(-100, 100) for _ in range(n)]

    if level == 1:
        problem = f"Find the maximum element in the list: {arr}"
        answer = str(max(arr))
    elif level == 2:
        problem = f"Sum all elements in the list: {arr}"
        answer = str(sum(arr))
    else:
        problem = f"Find all pairs in {arr} that sum to {random.randint(-50, 50)}"
        target = random.randint(-50, 50)
        pairs = []
        for i in range(len(arr)):
            for j in range(i+1, len(arr)):
                if arr[i] + arr[j] == target:
                    pairs.append((arr[i], arr[j]))
        answer = str(len(pairs)) if pairs else "0"

    return CodingProblem(
        id=f"code-array-{seed}",
        problem=problem,
        answer=answer,
        family="array_manipulation",
        level=level,
        category="data_structure"
    )

def generate_string_manipulation(seed: int, level: int = 2):
    """String processing problems"""
    random.seed(seed)

    if level == 1:
        s = "hello world test string"
        problem = f"Count vowels in: '{s}'"
        answer = str(sum(1 for c in s if c in 'aeiouAEIOU'))
    elif level == 2:
        s = "racecar"
        problem = f"Is '{s}' a palindrome? Answer yes or no."
        answer = "yes" if s == s[::-1] else "no"
    else:
        s = "abracadabra"
        problem = f"Find the longest repeating substring in '{s}'"
        answer = "abra"

    return CodingProblem(
        id=f"code-string-{seed}",
        problem=problem,
        answer=answer,
        family="string_manipulation",
        level=level,
        category="string"
    )

def generate_algorithm_design(seed: int, level: int = 2):
    """Algorithm design and time complexity problems"""
    random.seed(seed)

    if level == 1:
        problem = "What is the time complexity of binary search on a sorted array?"
        answer = "O(log n)"
    elif level == 2:
        problem = "You have an unsorted array of 1 million numbers. What's the fastest way to find the top 10 largest numbers?"
        answer = "Use a min-heap of size 10"
    else:
        problem = "Design an algorithm to find the longest increasing subsequence in [3,10,2,1,20]. What is the length?"
        arr = [3, 10, 2, 1, 20]
        answer = "3"  # e.g., [3, 10, 20] or [1, 20] - longest is 3 elements

    return CodingProblem(
        id=f"code-algo-{seed}",
        problem=problem,
        answer=answer,
        family="algorithm_design",
        level=level,
        category="algorithm"
    )

def generate_bug_finding(seed: int, level: int = 2):
    """Debugging and code comprehension"""
    random.seed(seed)

    if level == 1:
        problem = """
def factorial(n):
    result = 1
    for i in range(1, n):  # BUG HERE
        result *= i
    return result

factorial(5) should return 120. What's the bug?
"""
        answer = "The range should be range(1, n+1) or range(2, n+1) - current loop stops at n-1"
    elif level == 2:
        problem = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)  # Inefficient but correct

What is the time complexity?
"""
        answer = "O(2^n) - exponential"
    else:
        problem = """
def sort_array(arr):
    for i in range(len(arr)):
        for j in range(len(arr)-1):  # BUG
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

What's the issue with this bubble sort?
"""
        answer = "Inner loop range is incorrect - should be range(len(arr)-1-i) for efficiency"

    return CodingProblem(
        id=f"code-bug-{seed}",
        problem=problem,
        answer=answer,
        family="bug_finding",
        level=level,
        category="debugging"
    )

def generate_coding_dataset(output_path: str, n_per_family: int = 200):
    """Generate comprehensive coding training dataset"""
    random.seed(42)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    generators = [
        ("array_manip", generate_array_manipulation, 2),
        ("string_manip", generate_string_manipulation, 2),
        ("algorithm", generate_algorithm_design, 2),
        ("debugging", generate_bug_finding, 2),
    ]

    with open(output_path, "w") as f:
        for gen_name, gen_func, default_level in generators:
            for level in [1, 2, 3]:
                for i in range(n_per_family // 3):
                    try:
                        prob = gen_func(seed=i * 3000 + level * 100, level=level)
                        f.write(json.dumps(asdict(prob)) + "\n")
                    except:
                        pass

    print(f"Generated {n_per_family * len(generators)} coding problems to {output_path}")

if __name__ == "__main__":
    generate_coding_dataset("data/raw/synth_coding/train.jsonl", n_per_family=200)
    generate_coding_dataset("data/raw/synth_coding/test.jsonl", n_per_family=50)
