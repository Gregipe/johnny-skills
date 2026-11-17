---
name: mlops
description: "MLOps skills — model serving, fine-tuning, evaluation, and experimentation. Covers llama.cpp, vLLM, HuggingFace, W&B, and evaluation harnesses."
category: mlops
trigger: model serving, fine-tuning, evaluation, ML experimentation, model deployment
---

# MLOps Skills

Complete guide to ML model operations — from local inference to production serving.

## Overview

This skill consolidates:
1. **Local Inference** — llama.cpp for GGUF models
2. **Production Serving** — vLLM for high-throughput serving
3. **Model Hub** — HuggingFace Hub interactions
4. **Evaluation** — lm-eval-harness benchmarks
5. **Experimentation** — Weights & Biases tracking

---

## 1. Local Inference (llama.cpp)

### Setup

```bash
# Build from source
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make

# Download a GGUF model
# From HuggingFace: TheBloke/Mistral-7B-Instruct-v0.1-GGUF
```

### Run

```bash
./main -m mistral-7b-instruct-v01.Q4_K_M.gguf -n 256 -t 8
```

### Quantization

```bash
./quantize mistral-7b-instruct-v01.F16.gguf mistral-7b-q4.gguf Q4_K_M
```

---

## 2. Production Serving (vLLM)

### Install

```bash
pip install vllm
```

### Serve

```bash
vllm serve meta-llama/Mistral-7B-Instruct-v0.1
# → OpenAI-compatible API at http://localhost:8000
```

### API

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "meta-llama/Mistral-7B-Instruct-v0.1", "messages": [{"role": "user", "content": "Hello"}]}'
```

---

## 3. HuggingFace Hub

### CLI

```bash
# Search models
huggingface-cli download meta-llama/Mistral-7B-Instruct-v0.1

# Upload model
huggingface-cli upload my-model /path/to/model

# Search
huggingface-cli search mistral
```

### Python

```python
from huggingface_hub import HfApi
api = HfApi()
api.list_models()
```

---

## 4. Evaluation (lm-eval-harness)

### Install

```bash
git clone https://github.com/EleutherAI/lm-evaluation-harness
cd lm-evaluation-harness
pip install -e .
```

### Run

```bash
lm_eval --model hf \
  --model_args pretrained=mistralai/Mistral-7B-Instruct-v0.1 \
  --tasks mmlu \
  --device cuda:0
```

### Tasks

- MMLU (massive multitask language understanding)
- GSM8K (grade school math)
- HumanEval (code generation)
- ARC (reasoning)

---

## 5. Weights & Biases

### Setup

```bash
pip install wandb
wandb login
```

### Track

```python
import wandb
wandb.init(project="my-project")
wandb.log({"loss": 0.5, "epoch": 1})
```

### Sweeps

```yaml
# sweep.yaml
program: train.py
method: grid
parameters:
  learning_rate:
    values: [1e-4, 1e-3, 1e-2]
```

```bash
wandb sweep sweep.yaml
wandb agent
```

---

## 6. Model Quantization (Abliteration)

### Use Obliteratus

```bash
git clone https://github.com/telo/obliteratus
cd obliteratus
pip install -r requirements.txt
python obliteratus.py --model meta-llama/Mistral-7B-Instruct-v0.1 --quantize q4_k_m
```

Removes refusals from models by diffusing layer outputs.

---

## References

- `references/model-comparison.md` — Head-to-head model benchmarks
- `references/quantization-guide.md` — GGUF quantization guide