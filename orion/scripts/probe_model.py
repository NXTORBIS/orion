r"""Load the selected base model on this machine and measure real inference/training speed.

Records: which transformers class loads it, parameter counts (text vs vision), whether the
Gated DeltaNet layers run on a fallback kernel, greedy-generation tokens/s, and forward+backward
time at a training-like sequence length. Output goes to docs/measurements/.

    .venv\Scripts\python.exe scripts\probe_model.py [model_dir]
"""

import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = Path(sys.argv[1] if len(sys.argv) > 1 else "models/Qwen3.5-0.8B-Base")
OUT = Path("docs/measurements")


def main() -> None:
    torch.manual_seed(0)
    caught: list[str] = []
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tok = AutoTokenizer.from_pretrained(MODEL)
        t0 = time.perf_counter()
        model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
        load_s = time.perf_counter() - t0
        caught = sorted({str(x.message)[:200] for x in w})
    model.eval()
    params = {}
    for name, p in model.named_parameters():
        top = name.split(".")[1] if name.startswith("model.") else name.split(".")[0]
        params[top] = params.get(top, 0) + p.numel()

    prompt = "The capital of France is"
    ids = tok(prompt, return_tensors="pt")
    with torch.no_grad():
        t0 = time.perf_counter()
        out = model.generate(**ids, max_new_tokens=32, do_sample=False)
        gen_s = time.perf_counter() - t0
    new = out[0][ids.input_ids.shape[1]:]
    completion = tok.decode(new, skip_special_tokens=True)

    # training-shaped step: forward + backward on 512 tokens, all params trainable, no optimizer
    model.train()
    x = torch.randint(0, tok.vocab_size, (1, 512))
    t0 = time.perf_counter()
    loss = model(input_ids=x, labels=x).loss
    loss.backward()
    train_s = time.perf_counter() - t0
    model.zero_grad(set_to_none=True)

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_dir": str(MODEL),
        "transformers": transformers.__version__,
        "torch": torch.__version__,
        "loaded_class": type(model).__name__,
        "load_seconds": round(load_s, 1),
        "params_by_block": {k: round(v / 1e6, 1) for k, v in params.items()},
        "params_total_M": round(sum(params.values()) / 1e6, 1),
        "generate": {"prompt": prompt, "completion": completion, "new_tokens": int(new.numel()),
                     "tokens_per_s": round(new.numel() / gen_s, 2)},
        "train_step_512_tokens": {"seconds": round(train_s, 2), "tokens_per_s": round(512 / train_s, 1),
                                  "initial_loss_random_tokens": round(float(loss), 3)},
        "peak_rss_MB": None,
        "warnings": caught,
    }
    try:
        import psutil  # optional
        result["peak_rss_MB"] = round(psutil.Process().memory_info().peak_wset / 1e6)
    except Exception:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"model_probe_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("saved", path)


if __name__ == "__main__":
    main()
