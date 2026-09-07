"""QLoRA 학습 몇 스텝을 돌려 peak VRAM 을 측정한다. W1 게이트 도구.

사용 (finetune 그룹 필요):
    uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-4B --seq-len 2048 --batch 2
    uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-8B --seq-len 1024 --batch 1

결과는 stdout 과 docs/vram_probe_log.md 에 기록된다. OOM 이 나도 로그에 남는다.
모델 가중치는 첫 실행 시 Hugging Face 에서 내려받는다 (4B 약 8GB, 8B 약 16GB 디스크).
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "vram_probe_log.md"
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
HEADER = (
    "# VRAM 실측 로그\n\n"
    "scripts/vram_probe.py 가 자동으로 추가한다. 예산표(Notion 2.1)는 이 값으로 갱신한다.\n\n"
    "| 일시 | 모델 | seq | batch | rank | grad ckpt | peak VRAM (GB) | 스텝/초 | 상태 | 환경 |\n"
    "|---|---|---|---|---|---|---|---|---|---|\n"
)


def append_log(row: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not LOG.exists():
        LOG.write_text(HEADER, encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(row + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--seq-len", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--no-grad-ckpt", action="store_true")
    ap.add_argument("--env", default="", help="로그에 남길 환경 메모 (예: wsl2, win-native)")
    args = ap.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    grad_ckpt = not args.no_grad_ckpt
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status, peak, sps = "ok", float("nan"), float("nan")
    try:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        tok = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForCausalLM.from_pretrained(
            args.model, quantization_config=bnb, device_map={"": 0}, torch_dtype=torch.bfloat16
        )
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=grad_ckpt)
        lora = LoraConfig(
            r=args.rank,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            target_modules=TARGETS,
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora)
        model.print_trainable_parameters()
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=1e-4)

        vocab = len(tok)
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        for step in range(args.steps):
            ids = torch.randint(0, vocab, (args.batch, args.seq_len), device="cuda")
            out = model(input_ids=ids, labels=ids)
            out.loss.backward()
            opt.step()
            opt.zero_grad(set_to_none=True)
            torch.cuda.synchronize()
            cur = torch.cuda.max_memory_allocated() / 2**30
            print(f"step {step + 1}/{args.steps} loss={out.loss.item():.3f} peak={cur:.2f} GB")
        sps = args.steps / (time.time() - t0)
        peak = torch.cuda.max_memory_allocated() / 2**30
    except torch.cuda.OutOfMemoryError:
        status = "OOM"
        peak = torch.cuda.max_memory_allocated() / 2**30
        print("CUDA OOM")
    except Exception as e:
        status = f"error: {type(e).__name__}: {str(e)[:80]}"
        print(status)

    row = (
        f"| {now} | {args.model} | {args.seq_len} | {args.batch} | {args.rank} | {grad_ckpt} "
        f"| {peak:.2f} | {sps:.2f} | {status} | {args.env} |"
    )
    append_log(row)
    print(row)


if __name__ == "__main__":
    main()
