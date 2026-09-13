from orion.system.hardware import CATALOG, Hardware, Speed, choose

MEASURED = {"qwen3-1.7b": Speed(51.2, 14.6), "qwen3-4b": Speed(31.6, 9.5), "qwen3-14b": Speed(7.1, 2.96)}


def _hw(ram_gb, gpus=()):
    return Hardware(ram_gb=ram_gb, logical_cpus=12, physical_cpus=10, gpus=list(gpus), cpu_name="test")


def _install(tmp_path, names):
    for c in CATALOG:
        if c.name in names:
            p = tmp_path / c.path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"")
    return tmp_path


def test_picks_the_largest_model_that_meets_the_speed_target(tmp_path):
    root = _install(tmp_path, {"qwen3-1.7b", "qwen3-4b", "qwen3-14b"})
    benched = []
    pick, tried = choose(_hw(34), root, lambda c: benched.append(c.name) or MEASURED[c.name])
    assert pick.name == "qwen3-4b" and benched == ["qwen3-14b", "qwen3-4b"]
    assert not tried[0]["meets_target"] and tried[1]["meets_target"]


def test_memory_limits_candidates_and_a_slow_machine_gets_the_smallest(tmp_path):
    root = _install(tmp_path, {"qwen3-1.7b", "qwen3-4b", "qwen3-14b"})
    pick, tried = choose(_hw(8), root, lambda c: Speed(5, 2))
    assert pick.name == "qwen3-1.7b" and [t["model"] for t in tried] == ["qwen3-4b", "qwen3-1.7b"]


def test_gpu_memory_admits_bigger_models(tmp_path):
    root = _install(tmp_path, {"qwen3-4b", "qwen3-14b"})
    pick, _ = choose(_hw(8, [{"name": "RTX", "vram_gb": 24}]), root, lambda c: Speed(900, 40))
    assert pick.name == "qwen3-14b"


def test_nothing_installed(tmp_path):
    assert choose(_hw(34), tmp_path, lambda c: Speed(1, 1)) == (None, [])
