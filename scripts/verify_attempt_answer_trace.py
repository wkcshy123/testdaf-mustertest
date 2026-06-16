"""Verify that every student attempt can trace back to question answers.

This simulates what the scoring system will need: given an attempt's
question_id, find the corresponding question package and verify that
the grading-relevant fields (answer, acceptable_variants, etc.) are
present and well-formed.

Usage:
    uv run python scripts/verify_attempt_answer_trace.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.file_io.atomic_json import read_json
from student_platform.config import QUESTION_BANK_DIR, STUDENT_ATTEMPTS_DIR


# What grading fields each answer_mode needs.
GRADING_FIELDS = {
    "short_text": ["answer", "acceptable_variants"],
    "richtig_falsch": ["answer"],
    "matching": ["answer"],
    "single_choice_abc": ["answer"],
    "ja_nein_not_given": ["answer"],
    "essay": [],          # graded by rubric, no fixed answer
    "spoken_response": [], # graded by rubric, no fixed answer
}

# Which bundle key holds the answer data for each answer_mode.
ANSWER_BUNDLE_KEY = {
    "short_text": "questions",
    "richtig_falsch": "statements",
    "matching": "questions",
    "single_choice_abc": "questions",
    "ja_nein_not_given": "statements",
}


def find_question_dir(question_id: str) -> Path | None:
    """Locate a question package by ID in the question_bank."""
    for path in QUESTION_BANK_DIR.rglob(question_id):
        if path.is_dir() and ".trash" not in path.parts and (path / "manifest.json").exists():
            return path
    return None


def verify_attempt(attempt_dir: Path) -> dict:
    """Check one attempt's ability to trace back to grading data."""
    meta = read_json(attempt_dir / "meta.json")
    question_id = meta.get("question_id", "")
    answer_mode = meta.get("answer_mode", "")
    section = meta.get("section", "")

    result = {
        "attempt_id": attempt_dir.name,
        "question_id": question_id,
        "section": section,
        "answer_mode": answer_mode,
        "ok": True,
        "errors": [],
    }

    # 1. Can we find the question?
    qdir = find_question_dir(question_id)
    if not qdir:
        result["ok"] = False
        result["errors"].append(f"题目包未找到: {question_id}")
        return result

    manifest = read_json(qdir / "manifest.json")

    # 2. Is the answer_mode consistent?
    actual_mode = manifest.get("parameters", {}).get("answer_mode", "")
    if actual_mode != answer_mode:
        result["ok"] = False
        result["errors"].append(
            f"answer_mode 不一致: attempt={answer_mode} manifest={actual_mode}"
        )

    # 3. For objective questions, verify grading fields exist
    if answer_mode in GRADING_FIELDS and GRADING_FIELDS[answer_mode]:
        bundle_key = ANSWER_BUNDLE_KEY.get(answer_mode)
        if not bundle_key:
            result["ok"] = False
            result["errors"].append(f"未知 answer_mode: {answer_mode}")
            return result

        # Find the answer file
        asset_name = manifest.get("assets", {}).get(bundle_key)
        if not asset_name:
            result["ok"] = False
            result["errors"].append(f"manifest.assets 缺少 '{bundle_key}'")
            return result

        answer_file = qdir / asset_name
        if not answer_file.exists():
            result["ok"] = False
            result["errors"].append(f"答案文件不存在: {asset_name}")
            return result

        items = read_json(answer_file)
        required = GRADING_FIELDS[answer_mode]

        for item in items:
            for field in required:
                if field not in item:
                    result["ok"] = False
                    result["errors"].append(
                        f"题号 {item.get('number','?')} 缺少字段 '{field}'"
                    )

        result["item_count"] = len(items)
        result["answer_file"] = asset_name

    # 4. Check student answers
    answers = read_json(attempt_dir / "answers.json")
    result["answered_count"] = len(answers) if isinstance(answers, dict) else 0

    # 5. Check audio file for speaking
    if answer_mode == "spoken_response":
        audio_file = meta.get("audio_file")
        if audio_file:
            result["audio_file"] = audio_file
            if not (attempt_dir / audio_file).exists():
                result["ok"] = False
                result["errors"].append(f"录音文件不存在: {audio_file}")
        else:
            result["ok"] = False
            result["errors"].append("口语题缺少录音文件")

    return result


def main() -> int:
    if not STUDENT_ATTEMPTS_DIR.exists():
        print("student_attempts/ 目录不存在，暂无作答记录。")
        return 0

    attempt_dirs = sorted(STUDENT_ATTEMPTS_DIR.glob("attempt_*"))
    if not attempt_dirs:
        print("暂无作答记录。")
        return 0

    print(f"扫描 {len(attempt_dirs)} 条作答记录\n")

    ok_count = 0
    for attempt_dir in attempt_dirs:
        result = verify_attempt(attempt_dir)
        status = "✅" if result["ok"] else "❌"
        line = f"{status} {result['attempt_id']}"
        line += f" | {result['section']}/{result['answer_mode']}"
        if "item_count" in result:
            line += f" | 题目{result['item_count']}题"
        line += f" | 已答{result['answered_count']}题"
        if "audio_file" in result:
            line += f" | 录音={result['audio_file']}"
        print(line)

        if result["errors"]:
            for err in result["errors"]:
                print(f"      ⚠️ {err}")
        else:
            ok_count += 1

    print(f"\n结果：{ok_count}/{len(attempt_dirs)} 条记录可完整回溯题目答案")
    return 0 if ok_count == len(attempt_dirs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
