"""Normalize question bundles into student-facing render data, stripping answers."""

from __future__ import annotations

import os

from shared.question_bank import QuestionBankReader


# Default time limits (seconds) per section for single-question practice.
DEFAULT_TIME_LIMITS = {
    "listening": 300,   # 5 min (not used — listening has no timer)
    "reading": 600,     # 10 min
    "writing": 3600,    # 60 min
    "speaking": 600,    # 10 min (future)
}

# Official TestDaF paper-based listening read-prep time (seconds) per task.
# Source: TestDaF Modellsatz 02 Hörverstehen
LISTENING_PREP_TIME = {
    "aufgabe_1": 30,
    "aufgabe_2": 60,
    "aufgabe_3": 90,
}
EXTRA_PREP_GRACE = 15

# Per-task-type overrides, configurable via environment variables.
# e.g. STUDENT_TIME_LIMIT_READING_AUFGABE_1=600
_ENV_PREFIX = "STUDENT_TIME_LIMIT_"


def _time_limit_for(section: str, task_type: str) -> int:
    """Resolve time limit: env override > section default."""
    env_key = f"{_ENV_PREFIX}{section.upper()}_{task_type.upper()}"
    env_val = os.getenv(env_key)
    if env_val:
        try:
            return max(0, int(env_val))
        except ValueError:
            pass
    return DEFAULT_TIME_LIMITS.get(section, 600)


# Backward-compatible flat dict (section -> seconds) for external callers.
TIME_LIMITS = dict(DEFAULT_TIME_LIMITS)


class QuestionPresenter:
    """Extract a render-safe view from a question bundle.

    The returned dict never contains answer/evidence/acceptable_variants
    or any other grading fields — those stay in the bundle for the
    scoring system.
    """

    def __init__(self, reader: QuestionBankReader):
        self.reader = reader

    def present(self, question_meta: dict) -> dict | None:
        """Build the view model for the student answer page.

        Returns None if the question type is not yet supported.
        """
        section = question_meta.get("section", "")
        task_type = question_meta.get("task_type", "")
        answer_mode = (
            question_meta.get("parameters", {}).get("answer_mode", "")
        )
        bundle = self.reader.load_question_bundle(question_meta["_path"])

        view = {
            "question_id": question_meta["id"],
            "title": question_meta.get("title", ""),
            "topic": question_meta.get("topic", ""),
            "section": section,
            "task_type": task_type,
            "answer_mode": answer_mode,
            "path": question_meta["_path"],
            "time_limit_seconds": _time_limit_for(section, task_type),
        }

        # ------------------------------------------------------------------
        # Listening: three-stage UI (read-prep → countdown → auto-play audio)
        # Only set for listening questions — speaking has its own intro
        # audio handled by the multi-stage state machine.
        # ------------------------------------------------------------------
        if section == "listening":
            assets = question_meta.get("assets", {})
            if assets.get("audio"):
                view["audio_file"] = assets["audio"]
            params = question_meta.get("parameters", {})
            view["play_count"] = params.get("play_count", 1)
            view["prep_time_seconds"] = LISTENING_PREP_TIME.get(task_type, 60)
            view["extra_prep_grace"] = EXTRA_PREP_GRACE
            view["task_type"] = task_type
            if view["play_count"] >= 2:
                view["play_interval_seconds"] = 60

        if answer_mode == "short_text":
            view["items"] = self._present_short_text(bundle)
        elif answer_mode == "richtig_falsch":
            view["items"] = self._present_richtig_falsch(bundle)
        elif answer_mode == "matching":
            view.update(self._present_matching(bundle))
        elif answer_mode == "single_choice_abc":
            view["reading_paragraphs"] = self._split_paragraphs(bundle.get("reading_text", ""))
            view["items"] = self._present_single_choice(bundle)
        elif answer_mode == "ja_nein_not_given":
            view["reading_paragraphs"] = self._split_paragraphs(bundle.get("reading_text", ""))
            view["items"] = self._present_ja_nein(bundle)
        elif answer_mode == "essay":
            view.update(self._present_essay(bundle, question_meta))
        elif answer_mode == "spoken_response":
            view.update(self._present_speaking(bundle, question_meta))
        else:
            # unknown answer_mode — not supported
            return None

        return view

    # ------------------------------------------------------------------
    # Per-mode presenters — each strips all grading fields
    # ------------------------------------------------------------------

    @staticmethod
    def _present_short_text(bundle: dict) -> list[dict]:
        items = []
        for q in bundle.get("questions", []):
            items.append(
                {
                    "number": q["number"],
                    "prompt": q.get("prompt", ""),
                    "required_points": q.get("required_points", 1),
                }
            )
        return items

    @staticmethod
    def _present_richtig_falsch(bundle: dict) -> list[dict]:
        items = []
        for s in bundle.get("statements", []):
            items.append(
                {
                    "number": s["number"],
                    "statement": s.get("statement", ""),
                }
            )
        return items

    @staticmethod
    def _present_matching(bundle: dict) -> dict:
        profiles = []
        for p in bundle.get("profiles", []):
            profiles.append({"number": p["number"], "need": p.get("need", "")})

        offers = []
        for t in bundle.get("texts", []):
            offers.append(
                {"label": t["label"], "heading": t.get("heading", ""), "text": t.get("text", "")}
            )

        option_labels = [o["label"] for o in offers] + ["I"]
        return {
            "items": profiles,
            "offers": offers,
            "option_labels": option_labels,
        }

    @staticmethod
    def _present_single_choice(bundle: dict) -> list[dict]:
        items = []
        for q in bundle.get("questions", []):
            items.append(
                {
                    "number": q["number"],
                    "prompt": q.get("prompt", ""),
                    "options": q.get("options", {}),
                }
            )
        return items

    @staticmethod
    def _present_ja_nein(bundle: dict) -> list[dict]:
        items = []
        for s in bundle.get("statements", []):
            items.append(
                {
                    "number": s["number"],
                    "statement": s.get("statement", ""),
                }
            )
        return items

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split raw reading text into non-empty stripped paragraphs."""
        return [p.strip() for p in text.strip().split("\n") if p.strip()]

    @staticmethod
    def _present_essay(bundle: dict, question_meta: dict) -> dict:
        """Extract writing prompt data for the student answer page.

        The prompt.json is loaded under the 'prompt' bundle key. We expose
        background, task_prompt, and writing_instructions, plus chart image
        paths from manifest assets. No grading rubric is included.
        """
        prompt = bundle.get("prompt", {})
        assets = question_meta.get("assets", {})
        chart_images = assets.get("chart_images", [])

        return {
            "essay_background": prompt.get("background", ""),
            "essay_task_prompt": prompt.get("task_prompt", ""),
            "essay_instructions": prompt.get("writing_instructions", []),
            "chart_images": chart_images,
        }

    @staticmethod
    def _parse_german_duration(text: str) -> int:
        """Parse German time strings into seconds.

        Handles: "30 Sekunden", "1 Minute", "1 Minute 30 Sekunden",
        "3 Minuten", "1 Minute 30 Sekunden".
        """
        import re

        total = 0
        min_match = re.search(r"(\d+)\s*Minute[n]?", text)
        sec_match = re.search(r"(\d+)\s*Sekunde[n]?", text)
        if min_match:
            total += int(min_match.group(1)) * 60
        if sec_match:
            total += int(sec_match.group(1))
        return total if total > 0 else 60

    @staticmethod
    def _present_speaking(bundle: dict, question_meta: dict) -> dict:
        """Extract speaking prompt data for the multi-stage answer page.

        Returns scenario, prompt_points, examiner intro text, parsed
        prep/speaking durations, chart images, and intro audio path.
        """
        prompt = bundle.get("prompt", {})
        assets = question_meta.get("assets", {})
        params = question_meta.get("parameters", {})

        prep_raw = prompt.get("prep_time") or params.get("prep_time", "1 Minute")
        speak_raw = prompt.get("speaking_time") or params.get("speaking_time", "1 Minute")

        return {
            "speaking_scenario": prompt.get("scenario", ""),
            "speaking_prompt_points": prompt.get("prompt_points", []),
            "speaking_examiner_intro": prompt.get("examiner_intro", ""),
            "speaking_task_type": prompt.get("task_type", ""),
            "speaking_number": prompt.get("number", 0),
            "prep_time_text": prep_raw,
            "prep_time_seconds": QuestionPresenter._parse_german_duration(prep_raw),
            "speaking_time_text": speak_raw,
            "speaking_time_seconds": QuestionPresenter._parse_german_duration(speak_raw),
            "needs_chart": prompt.get("needs_chart", False),
            "chart_images": assets.get("chart_images", []),
            "intro_audio": assets.get("audio", ""),
        }
