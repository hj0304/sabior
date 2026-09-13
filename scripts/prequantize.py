"""bf16 체크포인트를 bitsandbytes nf4 로 양자화해 로컬에 저장한다.

Unsloth 가 비양자화 모델을 load_in_4bit 로 읽을 때 양자화 피크가 VRAM 캡을 넘는 경우(A.X 4.0 Light 에서 확인),
미리 양자화된 체크포인트를 읽게 하면 피크를 피한다. Unsloth 의 unsloth/*-bnb-4bit 저장소와 같은 방식.

사용:
    bash scripts/wsl_run.sh python scripts/prequantize.py --model skt/A.X-4.0-Light --out data/models/A.X-4.0-Light-bnb-4bit
"""

from __future__ import annotations

import argparse

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCausalLM.from_pretrained(
        a.model, quantization_config=bnb, device_map={"": 0}, dtype=torch.bfloat16
    )
    print(f"allocated after load: {torch.cuda.memory_allocated() / 2**30:.2f} GB")
    model.save_pretrained(a.out, safe_serialization=True)
    tok.save_pretrained(a.out)
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
