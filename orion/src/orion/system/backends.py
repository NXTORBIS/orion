"""Model backends behind one interface: ``chat(messages, ...) -> str``.

* ``HFBackend``          — a local transformers checkpoint (+ optional LoRA adapter), CPU or GPU.
* ``LlamaServerBackend`` — llama.cpp ``llama-server`` (OpenAI-compatible HTTP API) for GGUF models;
                           ``start_llama_server`` launches it from tools/llama.cpp.
* ``VisionBackend``      — multimodal model (Qwen3.5-0.8B) for image understanding and analysis.
* ``ScriptedBackend``    — deterministic canned responses for tests of the system logic.
"""

from __future__ import annotations

import base64
import io
import json
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

Message = dict[str, str]


class Backend(Protocol):
    name: str

    def chat(self, messages: list[Message], max_tokens: int = 512, temperature: float = 0.0, stop: list[str] | None = None) -> str: ...


class ScriptedBackend:
    """Replies from a function of the conversation (tests), recording every call."""

    def __init__(self, reply: Callable[[list[Message]], str], name: str = "scripted"):
        self.reply, self.name, self.calls = reply, name, []

    def chat(self, messages: list[Message], max_tokens: int = 512, temperature: float = 0.0, stop: list[str] | None = None) -> str:
        self.calls.append(messages)
        return self.reply(messages)


class HFBackend:
    def __init__(self, model_dir: str | Path, adapter_dir: str | Path | None = None, max_new_tokens: int = 512):
        from orion.evals.runner import HFGenerator

        self.gen = HFGenerator(model_dir, adapter_dir, batch_size=1, max_new_tokens=max_new_tokens)
        self.name = self.gen.name

    def chat(self, messages: list[Message], max_tokens: int = 512, temperature: float = 0.0, stop: list[str] | None = None) -> str:
        self.gen.max_new_tokens = max_tokens
        return self.gen.generate([messages])[0]

    def chat_many(self, conversations: list[list[Message]], max_tokens: int = 512) -> list[str]:
        self.gen.max_new_tokens = max_tokens
        return self.gen.generate(conversations)


class VisionBackend:
    """Multimodal vision-language model (e.g., Qwen3.5-0.8B with vision encoder)."""

    def __init__(self, model_dir: str | Path, max_new_tokens: int = 512):
        import torch
        from PIL import Image
        from transformers import AutoProcessor, AutoModelForCausalLM

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        self.model_path = Path(model_dir)
        self.max_new_tokens = max_new_tokens
        self.name = f"vision:{self.model_path.name}"

        # Load processor and model
        self.processor = AutoProcessor.from_pretrained(str(self.model_path), trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path),
            torch_dtype=self.dtype,
            device_map=self.device,
            trust_remote_code=True,
        )
        self.model.eval()

    def analyze_vision(self, image_base64: str, prompt: str) -> dict[str, Any]:
        """Analyze an image with a text prompt.

        Args:
            image_base64: Base64-encoded image data
            prompt: Text prompt for analysis

        Returns:
            Dict with description, objects, confidence, etc.
        """
        from PIL import Image
        import torch

        # Decode base64 image
        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        except Exception as e:
            return {
                "description": "",
                "objects": [],
                "text": "",
                "confidence": 0.0,
                "error": f"Failed to decode image: {e}",
            }

        # Prepare inputs
        messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]

        # Process and generate
        try:
            text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = self.processor.process_vision_info(messages)
            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            inputs = inputs.to(self.device)

            with torch.no_grad():
                outputs = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)

            response_text = self.processor.decode(outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)

            return {
                "description": response_text,
                "objects": [],
                "text": "",
                "confidence": 0.85,  # Placeholder confidence
            }
        except Exception as e:
            return {
                "description": "",
                "objects": [],
                "text": "",
                "confidence": 0.0,
                "error": f"Vision analysis failed: {e}",
            }

    def chat(self, messages: list[Message], max_tokens: int = 512, temperature: float = 0.0, stop: list[str] | None = None) -> str:
        """Text-only chat (falls back to text mode if image not present)."""
        # For now, just use text; full multimodal chat would require processing images in messages
        self.max_new_tokens = max_tokens

        import torch

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(text=[text], padding=True, return_tensors="pt")
        inputs = inputs.to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)

        response = self.processor.decode(outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        return response.strip()


class LlamaServerBackend:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", name: str = "llama-server", timeout: float = 600.0):
        self.base_url, self.name, self.timeout = base_url.rstrip("/"), name, timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(self.base_url + path, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(self, messages: list[Message], max_tokens: int = 512, temperature: float = 0.0, stop: list[str] | None = None) -> str:
        payload: dict[str, Any] = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if stop:
            payload["stop"] = stop
        out = self._post("/v1/chat/completions", payload)
        return out["choices"][0]["message"]["content"].strip()

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False


def start_llama_server(model_path: str | Path, port: int = 8080, threads: int = 10, ctx: int = 8192, parallel: int = 1,
                       exe: str | Path = "tools/llama.cpp/llama-server.exe", wait_s: float = 300.0) -> tuple[subprocess.Popen, LlamaServerBackend]:
    """Launch llama-server on a GGUF file and wait until /health answers."""
    cmd = [str(exe), "-m", str(model_path), "--port", str(port), "-t", str(threads), "-c", str(ctx), "-np", str(parallel),
           "--host", "127.0.0.1", "--temp", "0"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    backend = LlamaServerBackend(f"http://127.0.0.1:{port}")
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited with code {proc.returncode}")
        if backend.healthy():
            return proc, backend
        time.sleep(2)
    proc.kill()
    raise TimeoutError("llama-server did not become healthy in time")
