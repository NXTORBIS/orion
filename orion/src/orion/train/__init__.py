"""Training entry points (project brief §4, §15, §25–27).

* ``sft``  — supervised fine-tuning with LoRA (or full fine-tuning) via TRL ``SFTTrainer``.
* ``dpo``  — preference optimisation via TRL ``DPOTrainer``.
* ``grpo`` — RL with verifiable rewards via TRL ``GRPOTrainer`` and ORION verifiers.

All entry points take a YAML config, log to MLflow, and write a *run card* next to the
checkpoint recording model revision, dataset version, hyper-parameters, hardware, duration,
loss curve and git commit — the record every ORION version card is built from.
"""
