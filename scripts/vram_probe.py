"""QLoRA 학습 몇 스텝을 돌려 peak VRAM 을 측정한다. W2 게이트 도구.

사용 (finetune 그룹 필요):
    uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-4B-Instruct-2507 --seq-len 2048 --batch 2
    uv run --group finetune python scripts/vram_probe.py --model skt/A.X-4.0-Light --seq-len 1024 --batch 1 --ladder

--ladder 를 주면 지정한 (seq, batch) 에서 시작해 OOM 이 나면 더 작은 조합으로 내려가며 처음 성공하는 설정을 찾는다.
결과는 stdout 과 docs/vram_probe_log.md 에 한 줄씩 기록된다. OOM 도 기록된다.
모델 가중치는 첫 실행 시 Hugging Face 에서 내려받는다 (4B 약 8GB, 7-8B 약 15GB 디스크).
"""

from __future__ import annotations

import argparse
import gc
import math
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "vram_probe_log.md"
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
LADDER = [(2048, 2), (2048, 1), (1536, 1), (1024, 2), (1024, 1), (768, 1), (512, 1)]
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


def is_oom(e: BaseException) -> bool:
    return "out of memory" in str(e).lower() or type(e).__name__ in ("OutOfMemoryError",)


def probe(model_id: str, seq_len: int, batch: int, rank: int, steps: int, grad_ckpt: bool):
    """한 설정을 측정한다. (status, peak_gb, steps_per_sec) 를 돌려준다."""
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    status, peak, sps = "ok", math.nan, math.nan
    model = opt = None
    try:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id, quantization_config=bnb, device_map={"": 0}, dtype=torch.bfloat16
        )
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=grad_ckpt)
        lora = LoraConfig(
            r=rank,
            lora_alpha=rank * 2,
            lora_dropout=0.05,
            target_modules=TARGETS,
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora)
        model.print_trainable_parameters()
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=1e-4)
        loaded = torch.cuda.memory_allocated() / 2**30
        print(f"loaded weights: {loaded:.2f} GB allocated")

        vocab = len(tok)
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        for step in range(steps):
            ids = torch.randint(0, vocab, (batch, seq_len), device="cuda")
            out = model(input_ids=ids, labels=ids)
            out.loss.backward()
            opt.step()
            opt.zero_grad(set_to_none=True)
            torch.cuda.synchronize()
            cur = torch.cuda.max_memory_allocated() / 2**30
            print(f"step {step + 1}/{steps} loss={out.loss.item():.3f} peak={cur:.2f} GB")
        sps = steps / (time.time() - t0)
        peak = torch.cuda.max_memory_allocated() / 2**30
    except (
        Exception
    ) as e:  # OOM 은 torch 버전에 따라 OutOfMemoryError 또는 AcceleratorError 로 온다
        status = "OOM" if is_oom(e) else f"error: {type(e).__name__}: {str(e)[:70]}"
        try:
            peak = torch.cuda.max_memory_allocated() / 2**30
        except Exception:
            pass
        print(status)
    finally:
        del model, opt
        gc.collect()
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
    return status, peak, sps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--seq-len", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--no-grad-ckpt", action="store_true")
    ap.add_argument(
        "--ladder", action="store_true", help="OOM 이면 더 작은 (seq, batch) 로 내려가며 재시도"
    )
    ap.add_argument("--env", default="", help="로그에 남길 환경 메모 (예: win-native, wsl2)")
    args = ap.parse_args()

    import torch

    grad_ckpt = not args.no_grad_ckpt
    free, total = torch.cuda.mem_get_info()
    env = f"{args.env} free={free / 2**30:.1f}/{total / 2**30:.1f}GB".strip()
    print(f"GPU {torch.cuda.get_device_name(0)} | {env}")

    configs = [(args.seq_len, args.batch)]
    if args.ladder:
        configs += [c for c in LADDER if c[0] * c[1] < args.seq_len * args.batch]
    for seq_len, batch in configs:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        print(f"== {args.model} seq={seq_len} batch={batch} rank={args.rank} ==")
        status, peak, sps = probe(args.model, seq_len, batch, args.rank, args.steps, grad_ckpt)
        row = (
            f"| {now} | {args.model} | {seq_len} | {batch} | {args.rank} | {grad_ckpt} "
            f"| {peak:.2f} | {sps:.2f} | {status} | {env} |"
        )
        append_log(row)
        print(row)
        if status == "ok" or not args.ladder:
            break


if __name__ == "__main__":
    main()
