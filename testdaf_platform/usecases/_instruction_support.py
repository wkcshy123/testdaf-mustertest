"""Shared helpers for listening use cases."""

from __future__ import annotations


def attach_instructions_to_segments(segments: list[dict], instructions: list[str]) -> None:
    """Attach each instruction to its matching segment in place.

    ``instructions`` must be the same length as ``segments``. The instruction
    is written to each segment's ``tts_instruction`` key so it is persisted
    alongside the text in ``segments.json``.
    """
    if len(instructions) != len(segments):
        raise RuntimeError(
            f"instructions 数量({len(instructions)})与 segments 数量"
            f"({len(segments)})不一致"
        )
    for segment, instruction in zip(segments, instructions):
        segment["tts_instruction"] = (instruction or "").strip()
