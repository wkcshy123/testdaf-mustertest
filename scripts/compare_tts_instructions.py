"""对比同一听力文案在「无 instructions」与「有 instructions」下的合成效果。

加载题库里一道听力题（listening/aufgabe_*/<question_id>），用
InstructionGenerator 为每个发言片段生成表现力指令，然后分别用
普通 flash 模型与 instruct 模型合成两份完整音频，输出到独立目录，
便于人工 A/B 试听对比。

Usage:
    # 自动挑选一道 aufgabe_1 听力题
    uv run python scripts/compare_tts_instructions.py

    # 指定题目
    uv run python scripts/compare_tts_instructions.py \
        --question listening/aufgabe_1/q_20260616_190320_a8063473

    # 指定输出根目录与语速
    uv run python scripts/compare_tts_instructions.py --out tmp/tts_ab --speech-speed normal
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testdaf_platform.config import QUESTION_BANK_DIR
from testdaf_platform.services.config_store import ConfigStore
from testdaf_platform.services.multi_speaker_tts import MultiSpeakerTTSService
from testdaf_platform.services.tts_instructions import InstructionGenerator


def resolve_api_key() -> str:
    key = os.getenv("DASHSCOPE_API_KEY") or ConfigStore().load_api_key()
    if not key:
        print("未找到 API Key：请设置 DASHSCOPE_API_KEY 或在页面保存。", file=sys.stderr)
        raise SystemExit(2)
    return key


def load_question(question_path: str) -> dict:
    qdir = (QUESTION_BANK_DIR / question_path).resolve()
    if not qdir.exists():
        raise SystemExit(f"题目目录不存在：{qdir}")
    manifest = json.loads((qdir / "manifest.json").read_text(encoding="utf-8"))
    segments = json.loads((qdir / "segments.json").read_text(encoding="utf-8"))
    return {"manifest": manifest, "segments": segments, "qdir": qdir}


def pick_default_question() -> str:
    base = QUESTION_BANK_DIR / "listening"
    for aufgabe in ("aufgabe_1", "aufgabe_2", "aufgabe_3"):
        d = base / aufgabe
        if d.exists():
            for child in sorted(d.iterdir()):
                if (child / "segments.json").exists():
                    return f"listening/{aufgabe}/{child.name}"
    raise SystemExit("题库里没有找到可用的听力题。")


def human_duration(seconds: float) -> str:
    return f"{seconds:.1f}s"


def main() -> int:
    parser = argparse.ArgumentParser(description="对比 TTS 有无 instructions 的合成效果。")
    parser.add_argument("--question", help="题库相对路径，如 listening/aufgabe_1/q_xxx")
    parser.add_argument("--out", default="tmp/tts_ab", help="对比输出根目录")
    parser.add_argument("--speech-speed", default="normal", help="整体语速倾向：slow/normal/fast")
    args = parser.parse_args()

    api_key = resolve_api_key()
    question_path = args.question or pick_default_question()
    question = load_question(question_path)
    manifest = question["manifest"]
    segments = question["segments"]
    params = manifest.get("parameters", {})
    speaker_voice_map = params.get("speaker_voice_map", {})
    if not speaker_voice_map:
        raise SystemExit(f"题目 {question_path} 的 manifest 未包含 speaker_voice_map。")

    title = manifest.get("title", "")
    scenario = params.get("scenario") or manifest.get("topic", "")
    speaker_roles = params.get("speaker_roles", {})
    relationship = params.get("relationship", "")
    print(f"题目：{question_path}")
    print(f"标题：{title}")
    print(f"说话人音色：{speaker_voice_map}")
    print(f"片段数量：{len(segments)}")

    out_root = (PROJECT_ROOT / args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # ---- Step A: generate per-segment instructions ----
    print("\n[1/3] 生成语音表现力指令 …")
    instr_gen = InstructionGenerator()
    t0 = time.time()
    instructions = instr_gen.generate(
        api_key=api_key,
        title=title,
        scenario=scenario,
        speaker_roles=speaker_roles,
        relationship=relationship,
        segments=segments,
        speech_speed=args.speech_speed,
    )
    print(f"      完成，耗时 {human_duration(time.time() - t0)}，共 {len(instructions)} 条指令")
    for seg, ins in zip(segments, instructions):
        print(f"      · [{seg.get('speaker_id')}] {ins}")

    (out_root / "instructions.json").write_text(
        json.dumps(
            [{"index": s.get("index", i + 1), "speaker_id": s.get("speaker_id"), "instruction": ins}
             for i, (s, ins) in enumerate(zip(segments, instructions))],
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    tts_service = MultiSpeakerTTSService()

    # ---- Step B: baseline (no instructions, flash model) ----
    baseline_dir = out_root / "baseline_no_instructions"
    print(f"\n[2/3] 合成 A 组（无 instructions，flash 模型）→ {baseline_dir}")
    t0 = time.time()
    baseline = tts_service.synthesize_dialogue(
        api_key=api_key,
        segments=segments,
        speaker_voice_map=speaker_voice_map,
        output_dir=baseline_dir,
        instructions=None,
    )
    print(f"      完成，耗时 {human_duration(time.time() - t0)}")
    print(f"      音频：{baseline.path}（{baseline.size_kb:.1f} KB）")
    print(f"      使用 instruct 模型：{baseline.used_instruct_model}")

    # ---- Step C: variant (with instructions, instruct model) ----
    variant_dir = out_root / "variant_with_instructions"
    print(f"\n[3/3] 合成 B 组（有 instructions，instruct 模型）→ {variant_dir}")
    t0 = time.time()
    variant = tts_service.synthesize_dialogue(
        api_key=api_key,
        segments=segments,
        speaker_voice_map=speaker_voice_map,
        output_dir=variant_dir,
        instructions=instructions,
    )
    print(f"      完成，耗时 {human_duration(time.time() - t0)}")
    print(f"      音频：{variant.path}（{variant.size_kb:.1f} KB）")
    print(f"      使用 instruct 模型：{variant.used_instruct_model}")

    # ---- Report ----
    report = {
        "question": question_path,
        "title": title,
        "segment_count": len(segments),
        "baseline": {
            "dir": str(baseline_dir.relative_to(PROJECT_ROOT)),
            "audio": str(baseline.path.relative_to(PROJECT_ROOT)),
            "size_kb": round(baseline.size_kb, 1),
            "used_instruct_model": baseline.used_instruct_model,
        },
        "variant": {
            "dir": str(variant_dir.relative_to(PROJECT_ROOT)),
            "audio": str(variant.path.relative_to(PROJECT_ROOT)),
            "size_kb": round(variant.size_kb, 1),
            "used_instruct_model": variant.used_instruct_model,
        },
    }
    (out_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== 对比报告 ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n请分别试听两组 audio.wav 进行主观对比。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
