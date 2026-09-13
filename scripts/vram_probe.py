"""QLoRA 학습 몇 스텝을 돌려 peak VRAM 을 측정한다. W2 게이트 도구.

사용 (finetune 그룹 필요, WSL2 권장):
    uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-4B-Instruct-2507 --seq-len 2048 --batch 2 --ladder
    uv run --group finetune python scripts/vram_probe.py --model skt/A.X-4.0-Light --seq-len 1024 --batch 1

핵심 설계
  - **하드 캡**: NVIDIA Windows/WSL2 드라이버는 VRAM 이 모자라면 OOM 대신 시스템 RAM 으로 넘겨(sysmem fallback)
    측정을 무효로 만든다. 그래서 torch.cuda.set_per_process_memory_fraction 으로 (가용 VRAM - 여유) 이하로 할당을 제한해
    초과 시 진짜 OOM 이 나게 한다. --cap-gb 로 직접 지정할 수 있다.
  - **설정마다 새 프로세스**: 같은 프로세스에서 사다리를 내려가면 이전 시도의 메모리가 남는다. 부모가 --single 자식을
    설정별로 띄우고 결과 줄(RESULT ...)을 읽는다.
  - **fp32 업캐스트 없음**: peft.prepare_model_for_kbit_training 은 임베딩·lm_head 를 fp32 로 올려 8B 에서 2.5GB 를 낭비한다.
    기본은 bf16 유지 + gradient checkpointing 만 켠다. 비교용으로 --upcast 를 준다.
  - --ladder 는 OOM 일 때만 더 작은 (seq, batch) 로 내려간다. 환경 오류는 재시도하지 않는다.

결과는 stdout 과 docs/vram_probe_log.md 에 한 줄씩 기록된다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
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
    return "out of memory" in str(e).lower() or type(e).__name__ == "OutOfMemoryError"


def single(args: argparse.Namespace) -> dict:
    """자식 프로세스: 한 설정을 측정하고 결과 dict 를 돌려준다."""
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    free, total = torch.cuda.mem_get_info()
    total_gb = total / 2**30
    cap_gb = args.cap_gb if args.cap_gb else (free / 2**30 - args.margin_gb)
    torch.cuda.set_per_process_memory_fraction(min(0.999, cap_gb / total_gb))
    env = f"{args.env} free={free / 2**30:.1f}/{total_gb:.1f}GB cap={cap_gb:.1f}GB".strip()

    res = {
        "status": "ok",
        "peak": math.nan,
        "sps": math.nan,
        "weights": math.nan,
        "env": env,
        "gc": None,
    }
    try:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        tok = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            quantization_config=bnb,
            device_map={"": 0},
            dtype=torch.bfloat16,
            attn_implementation="sdpa",  # eager 는 어텐션 행렬(seq x seq)을 저장해 메모리를 크게 먹는다
        )
        model.config.use_cache = False
        if args.upcast:
            from peft import prepare_model_for_kbit_training

            model = prepare_model_for_kbit_training(
                model, use_gradient_checkpointing=not args.no_grad_ckpt
            )
        else:
            if not args.no_grad_ckpt:
                model.gradient_checkpointing_enable(
                    gradient_checkpointing_kwargs={"use_reentrant": False}
                )
            model.enable_input_require_grads()
        res["gc"] = bool(getattr(model, "is_gradient_checkpointing", False))
        lora = LoraConfig(
            r=args.rank,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            target_modules=TARGETS,
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora)
        # transformers 는 self.training 일 때만 gradient checkpointing 을 적용한다. from_pretrained 는 eval 모드로
        # 로드하므로 train() 을 부르지 않으면 활성값이 전부 저장되어 토큰당 수 MB 가 든다 (2026-09-13 측정에서 확인).
        model.train()
        model.print_trainable_parameters()
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=1e-4)
        torch.cuda.synchronize()
        res["weights"] = torch.cuda.memory_allocated() / 2**30
        print(
            f"loaded: {res['weights']:.2f} GB allocated | grad ckpt={res['gc']} | cap {cap_gb:.1f} GB"
        )

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
        res["sps"] = args.steps / (time.time() - t0)
        res["peak"] = torch.cuda.max_memory_allocated() / 2**30
        if res["peak"] > total_gb * 0.97:
            res["status"] = "spill (VRAM 초과, 공유 메모리 사용)"
    except (
        Exception
    ) as e:  # OOM 은 torch 버전에 따라 OutOfMemoryError 또는 AcceleratorError 로 온다
        res["status"] = "OOM" if is_oom(e) else f"error: {type(e).__name__}: {str(e)[:70]}"
        try:
            res["peak"] = torch.cuda.max_memory_allocated() / 2**30
        except Exception:
            pass
        print(res["status"])
    return res


def run_child(args: argparse.Namespace, seq_len: int, batch: int) -> dict:
    cmd = [
        sys.executable,
        __file__,
        "--single",
        "--model",
        args.model,
        "--seq-len",
        str(seq_len),
        "--batch",
        str(batch),
        "--rank",
        str(args.rank),
        "--steps",
        str(args.steps),
        "--margin-gb",
        str(args.margin_gb),
        "--env",
        args.env,
    ]
    if args.cap_gb:
        cmd += ["--cap-gb", str(args.cap_gb)]
    if args.no_grad_ckpt:
        cmd.append("--no-grad-ckpt")
    if args.upcast:
        cmd.append("--upcast")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    res = None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            res = json.loads(line[7:])
        elif line.startswith(("loaded:", "step ", "OOM", "error")):
            print("  " + line)
    if res is None:
        tail = (p.stderr or p.stdout).strip().splitlines()[-3:]
        res = {
            "status": f"error: child exit {p.returncode}: {' / '.join(tail)[:80]}",
            "peak": math.nan,
            "sps": math.nan,
            "weights": math.nan,
            "env": args.env,
            "gc": None,
        }
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--seq-len", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--no-grad-ckpt", action="store_true")
    ap.add_argument(
        "--upcast",
        action="store_true",
        help="peft.prepare_model_for_kbit_training 사용 (fp32 업캐스트)",
    )
    ap.add_argument(
        "--ladder", action="store_true", help="OOM 이면 더 작은 (seq, batch) 로 내려가며 재시도"
    )
    ap.add_argument(
        "--cap-gb", type=float, default=None, help="할당 상한 GB (기본: 가용 VRAM - margin)"
    )
    ap.add_argument("--margin-gb", type=float, default=0.3)
    ap.add_argument("--env", default="", help="로그에 남길 환경 메모 (예: wsl2)")
    ap.add_argument("--single", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.single:
        res = single(args)
        print("RESULT " + json.dumps(res, ensure_ascii=False))
        return

    configs = [(args.seq_len, args.batch)]
    if args.ladder:
        configs += [c for c in LADDER if c[0] * c[1] < args.seq_len * args.batch]
    grad_ckpt = not args.no_grad_ckpt
    for seq_len, batch in configs:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        print(
            f"== {args.model} seq={seq_len} batch={batch} rank={args.rank} upcast={args.upcast} =="
        )
        res = run_child(args, seq_len, batch)
        env = (
            f"{res.get('env', args.env)} w={res.get('weights', math.nan):.2f}GB gc={res.get('gc')}"
        )
        row = (
            f"| {now} | {args.model} | {seq_len} | {batch} | {args.rank} | {grad_ckpt} "
            f"| {res['peak']:.2f} | {res['sps']:.2f} | {res['status']} | {env} |"
        )
        append_log(row)
        print(row)
        if res["status"] == "ok" or not args.ladder or res["status"].startswith("error"):
            break


if __name__ == "__main__":
    main()
