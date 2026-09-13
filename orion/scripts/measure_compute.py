"""Measure this machine's real training throughput (effective GFLOP/s).

Feeds docs/03_hardware_report.md, replacing the assumed 100 GFLOP/s with a measured
value. Runs fully offline: random tensors only, no model or dataset downloads.

    .venv\\Scripts\\python.exe scripts\\measure_compute.py
"""

import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "measurements"


def matmul_gflops(n: int, dtype: torch.dtype, iters: int = 5) -> float:
    """Raw dense matmul throughput; an n x n x n product costs ~2n^3 FLOPs."""
    a = torch.randn(n, n, dtype=dtype)
    b = torch.randn(n, n, dtype=dtype)
    for _ in range(2):
        a @ b
    t0 = time.perf_counter()
    for _ in range(iters):
        a @ b
    dt = (time.perf_counter() - t0) / iters
    return 2 * n**3 / dt / 1e9


class Block(nn.Module):
    """Pre-norm decoder block with a SwiGLU MLP, shaped like small Qwen/Llama layers."""

    def __init__(self, d: int, ffn: int, heads: int):
        super().__init__()
        self.heads = heads
        self.attn_norm = nn.RMSNorm(d)
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.out = nn.Linear(d, d, bias=False)
        self.mlp_norm = nn.RMSNorm(d)
        self.gate_up = nn.Linear(d, 2 * ffn, bias=False)
        self.down = nn.Linear(ffn, d, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, d = x.shape
        q, k, v = self.qkv(self.attn_norm(x)).split(d, dim=-1)
        q, k, v = (z.view(b, t, self.heads, d // self.heads).transpose(1, 2) for z in (q, k, v))
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.out(a.transpose(1, 2).reshape(b, t, d))
        gate, up = self.gate_up(self.mlp_norm(x)).chunk(2, dim=-1)
        return x + self.down(F.silu(gate) * up)


def train_step_gflops(
    precision: str, layers: int = 4, d: int = 1024, ffn: int = 3072, heads: int = 16,
    seq: int = 512, batch: int = 1, steps: int = 4,
) -> dict:
    """Full forward + backward + AdamW step; FLOPs = (6N + 6*L*seq*d) per token (Kaplan et al.)."""
    torch.manual_seed(0)
    model = nn.Sequential(*[Block(d, ffn, heads) for _ in range(layers)])
    params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4)
    x = torch.randn(batch, seq, d)

    def step() -> None:
        with torch.autocast("cpu", dtype=torch.bfloat16, enabled=precision == "bf16-autocast"):
            loss = model(x).float().pow(2).mean()
        loss.backward()
        opt.step()
        opt.zero_grad(set_to_none=True)

    step()  # warm-up: allocator, kernel selection
    t0 = time.perf_counter()
    for _ in range(steps):
        step()
    sec_per_step = (time.perf_counter() - t0) / steps
    tokens = batch * seq
    flops_per_step = (6 * params + 6 * layers * seq * d) * tokens
    return {
        "precision": precision,
        "params": params,
        "tokens_per_step": tokens,
        "sec_per_step": round(sec_per_step, 3),
        "tokens_per_sec": round(tokens / sec_per_step, 1),
        "effective_gflops": round(flops_per_step / sec_per_step / 1e9, 1),
    }


def main() -> None:
    xpu = getattr(torch, "xpu", None)
    fp32 = matmul_gflops(2048, torch.float32)
    # Without AVX-512-BF16/AMX, bf16 matmul can fall back to a slow single-threaded kernel
    # (a first run at n=2048 stalled for 15+ minutes), so probe it small first and only
    # benchmark bf16 training when it is competitive with fp32.
    bf16 = matmul_gflops(256, torch.bfloat16, iters=2)
    train = [train_step_gflops("fp32")]
    if bf16 >= 0.25 * fp32:
        train.append(train_step_gflops("bf16-autocast"))
    else:
        train.append({"precision": "bf16-autocast", "skipped": f"bf16 matmul {bf16:.2f} vs fp32 {fp32:.1f} GFLOP/s"})
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": platform.node(),
        "cpu": platform.processor(),
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "xpu_available": bool(xpu and xpu.is_available()),
        "cuda_available": torch.cuda.is_available(),
        "matmul_gflops": {"fp32_n2048": round(fp32, 1), "bf16_n256": round(bf16, 2)},
        "train_step": train,
        "parallel_info": torch.__config__.parallel_info(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"compute_probe_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "parallel_info"}, indent=2))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
