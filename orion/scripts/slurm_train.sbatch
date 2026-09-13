#!/bin/bash
# ORION multi-node training launcher (Slurm + torchrun). Not runnable on the dev laptop.
# Usage: sbatch --nodes=8 scripts/slurm_train.sbatch configs/train/gpu_single_lora_sft.yaml
#SBATCH --job-name=orion-train
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --time=48:00:00
#SBATCH --output=runs/slurm/%x-%j.out

set -euo pipefail
CONFIG=${1:?training config yaml}
export MASTER_ADDR=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n 1)
export MASTER_PORT=29500
export NCCL_DEBUG=WARN
export TOKENIZERS_PARALLELISM=false
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-http://mlflow.internal:5000}

srun torchrun \
  --nnodes="$SLURM_JOB_NUM_NODES" --nproc_per_node=8 \
  --rdzv_id="$SLURM_JOB_ID" --rdzv_backend=c10d --rdzv_endpoint="$MASTER_ADDR:$MASTER_PORT" \
  -m accelerate.commands.launch --config_file configs/train/accelerate_fsdp2_8gpu.yaml \
  --num_machines "$SLURM_JOB_NUM_NODES" --num_processes $((SLURM_JOB_NUM_NODES * 8)) --machine_rank "$SLURM_NODEID" \
  -m orion.train.sft "$CONFIG"
