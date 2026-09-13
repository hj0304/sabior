# VRAM 실측 로그

scripts/vram_probe.py 가 자동으로 추가한다. 예산표(Notion 2.1)는 이 값으로 갱신한다.

| 일시 | 모델 | seq | batch | rank | grad ckpt | peak VRAM (GB) | 스텝/초 | 상태 | 환경 |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-13 16:47 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 2 | 16 | True | nan | nan | error: AcceleratorError: CUDA error: out of memory
Search for `cudaErrorMemoryAllocation' in https://docs | win-native |
| 2026-09-13 17:32 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 2 | 16 | True | 3.38 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:33 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 1 | 16 | True | 3.36 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:34 | Qwen/Qwen3-4B-Instruct-2507 | 1536 | 1 | 16 | True | 3.36 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:35 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 2 | 16 | True | 3.36 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:36 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 1 | 16 | True | 3.35 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:37 | Qwen/Qwen3-4B-Instruct-2507 | 768 | 1 | 16 | True | 3.35 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:38 | Qwen/Qwen3-4B-Instruct-2507 | 512 | 1 | 16 | True | 3.35 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:40 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 2 | 16 | True | 3.38 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:41 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 1 | 16 | True | 3.36 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:43 | Qwen/Qwen3-4B-Instruct-2507 | 1536 | 1 | 16 | True | 3.36 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:46 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 2 | 16 | True | 3.36 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:50 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 1 | 16 | True | 3.35 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 19:12 | Qwen/Qwen3-4B-Instruct-2507 | 768 | 1 | 16 | True | 3.35 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 17:04 | skt/A.X-4.0-Light | 1024 | 1 | 16 | True | 24.40 | 0.00 | ok | win-native |
| 2026-09-13 19:17 | Qwen/Qwen3-4B-Instruct-2507 | 512 | 1 | 16 | True | 3.35 | nan | error: RuntimeError: Failed to find C compiler. Please specify via CC environment variable  | wsl2 free=6.9/8.0GB |
| 2026-09-13 19:24 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 2 | 16 | True | 51.41 | nan | OOM | wsl2 free=6.9/8.0GB |
| 2026-09-13 19:28 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 1 | 16 | True | 31.13 | 0.00 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 19:40 | Qwen/Qwen3-4B-Instruct-2507 | 1536 | 1 | 16 | True | 24.44 | 0.01 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 19:47 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 2 | 16 | True | 31.13 | 0.01 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 19:55 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 1 | 16 | True | 17.43 | 0.02 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 19:59 | Qwen/Qwen3-4B-Instruct-2507 | 768 | 1 | 16 | True | 13.98 | 0.03 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:03 | Qwen/Qwen3-4B-Instruct-2507 | 512 | 1 | 16 | True | 10.62 | 0.07 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:04 | skt/A.X-4.0-Light | 1024 | 1 | 16 | True | 21.09 | 0.01 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:11 | skt/A.X-4.0-Light | 768 | 1 | 16 | True | 20.31 | 0.02 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:16 | skt/A.X-4.0-Light | 512 | 1 | 16 | True | 16.90 | 0.02 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:20 | Qwen/Qwen3-8B | 1024 | 1 | 16 | True | 25.48 | 0.01 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:33 | Qwen/Qwen3-8B | 768 | 1 | 16 | True | 21.24 | 0.01 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:46 | Qwen/Qwen3-8B | 512 | 1 | 16 | True | 16.99 | 0.02 | spill (VRAM 초과, 공유 메모리 사용) | wsl2 free=6.9/8.0GB |
| 2026-09-13 20:53 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 2 | 16 | True | 6.21 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 20:54 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 1 | 16 | True | 6.41 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 20:55 | Qwen/Qwen3-4B-Instruct-2507 | 1536 | 1 | 16 | True | 6.47 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 20:56 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 2 | 16 | True | 6.41 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 20:57 | Qwen/Qwen3-4B-Instruct-2507 | 1024 | 1 | 16 | True | 6.44 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 20:58 | Qwen/Qwen3-4B-Instruct-2507 | 768 | 1 | 16 | True | 6.48 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 20:59 | Qwen/Qwen3-4B-Instruct-2507 | 512 | 1 | 16 | True | 6.43 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 21:00 | skt/A.X-4.0-Light | 1024 | 1 | 16 | True | 6.48 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=4.65GB gc=True |
| 2026-09-13 21:02 | skt/A.X-4.0-Light | 768 | 1 | 16 | True | 6.48 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=4.65GB gc=True |
| 2026-09-13 21:04 | skt/A.X-4.0-Light | 512 | 1 | 16 | True | 6.51 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=4.65GB gc=True |
| 2026-09-13 21:05 | Qwen/Qwen3-8B | 1024 | 1 | 16 | True | 6.54 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=5.82GB gc=True |
| 2026-09-13 21:07 | Qwen/Qwen3-8B | 768 | 1 | 16 | True | 6.54 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=5.82GB gc=True |
| 2026-09-13 21:09 | Qwen/Qwen3-8B | 512 | 1 | 16 | True | 6.54 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=5.82GB gc=True |
| 2026-09-13 21:12 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 2 | 16 | True | 4.52 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 21:14 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 1 | 16 | True | 5.88 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 21:15 | Qwen/Qwen3-4B-Instruct-2507 | 1536 | 1 | 16 | True | 6.18 | 0.28 | ok | wsl2 free=6.9/8.0GB cap=6.6GB w=2.59GB gc=True |
| 2026-09-13 21:16 | skt/A.X-4.0-Light | 1024 | 1 | 16 | True | 6.37 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=4.65GB gc=True |
| 2026-09-13 21:18 | skt/A.X-4.0-Light | 768 | 1 | 16 | True | 6.15 | 0.35 | ok | wsl2 free=6.9/8.0GB cap=6.6GB w=4.65GB gc=True |
| 2026-09-13 21:19 | Qwen/Qwen3-8B | 1024 | 1 | 16 | True | 6.42 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=5.82GB gc=True |
| 2026-09-13 21:22 | Qwen/Qwen3-8B | 768 | 1 | 16 | True | 6.27 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=5.82GB gc=True |
| 2026-09-13 21:23 | Qwen/Qwen3-8B | 512 | 1 | 16 | True | 6.41 | nan | OOM | wsl2 free=6.9/8.0GB cap=6.6GB w=5.82GB gc=True |
| 2026-09-13 21:30 | Qwen/Qwen3-4B-Instruct-2507 | 2048 | 2 | 16 | True | 6.34 | 0.15 | ok | wsl2 unsloth free=6.8/8.0GB cap=6.5GB w=3.47GB gc=True |
| 2026-09-13 21:33 | skt/A.X-4.0-Light | 1024 | 1 | 16 | True | 6.52 | nan | OOM | wsl2 unsloth free=6.8/8.0GB cap=6.5GB w=nanGB gc=None |
| 2026-09-13 21:34 | skt/A.X-4.0-Light | 768 | 1 | 16 | True | 6.51 | nan | OOM | wsl2 unsloth free=6.8/8.0GB cap=6.5GB w=nanGB gc=None |
| 2026-09-13 21:35 | skt/A.X-4.0-Light | 512 | 1 | 16 | True | 6.52 | nan | OOM | wsl2 unsloth free=6.8/8.0GB cap=6.5GB w=nanGB gc=None |
| 2026-09-13 21:36 | Qwen/Qwen3-8B | 768 | 1 | 16 | True | 0.04 | nan | error: ValueError: Some modules are dispatched on the CPU or the disk. Make sure you have | wsl2 unsloth free=6.8/8.0GB cap=6.5GB w=nanGB gc=None |
| 2026-09-13 21:43 | /mnt/c/Users/SSAFY/Desktop/sabior/data/models/A.X-4.0-Light-bnb-4bit | 1024 | 1 | 16 | True | 5.60 | 0.28 | ok | wsl2 unsloth free=6.8/8.0GB cap=6.5GB w=4.68GB gc=True |
