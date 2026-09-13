from orion.system.fastpath import solve_directly


def test_arithmetic():
    assert solve_directly("Compute (17 + 50) + 8.").endswith("#### 75")
    assert solve_directly("What is 2+2?").endswith("#### 4")
    assert solve_directly("Compute (4 + 23) × 49.\n\nGive your final answer on the last line in the form: #### <answer>").endswith("#### 1323")
    assert solve_directly("What is 7/2?").endswith("#### 3.5")
    assert solve_directly("What is 0.1 + 0.2?").endswith("#### 0.3")
    assert solve_directly("Calculate 1440/17").endswith("#### 1440/17")
    assert solve_directly("What is 2^10?").endswith("#### 1024")


def test_equations_and_systems():
    assert solve_directly("Solve for x: 6x + 18 = 1x - 27.").endswith("#### -9")
    assert solve_directly("Solve for x: x^2 - 5x + 6 = 0").endswith("#### 2, 3")
    assert solve_directly("Solve the system:\n2x + 3y = 15\n1x + 2y = 9").endswith("#### x=3, y=3")
    assert solve_directly("Solve the system 6x - 3y = -48 and -5x - 2y = 22, then give the value of x + y.").endswith("#### -2")
    assert solve_directly("Solve the system:\n5x + 1y + 0z = -10\n1x + 7y + 1z = 2\n0x + 1y + 5z = 20").endswith("#### x=-2, y=0, z=4")


def test_leaves_everything_else_to_the_model():
    for q in ["hello", "What is the capital of France?", "Compute the cost of 3 boxes at (47 + 12) dollars each.",
              "What is 15% of 80?", "Solve for x: x^2 = -1", "Solve the system:\n2x + 4y = 16\n1x + 2y = 8",
              "What is 1/0?", "What is 9^99999?", "What is 9^9^9?", "Solve for x: __import__('os') = 1",
              "Solve for x: sin(x) = 1", "Explain why 2 + 2 = 4", "What is 2020-2021 season?"]:
        assert solve_directly(q) is None, q
