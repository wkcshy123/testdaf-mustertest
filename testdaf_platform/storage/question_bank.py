"""本地文件系统题库。"""

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from shared.file_io.atomic_json import read_json, write_json_atomic
from shared.file_io.path_guard import resolve_inside
from testdaf_platform.config import QUESTION_BANK_DIR

TRASH_RETENTION_DAYS = 7


@dataclass
class QuestionManifest:
    id: str
    section: str
    task_type: str
    title: str
    topic: str
    reference_material: str
    parameters: dict
    assets: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    version: int = 1


class QuestionBank:
    """按模块和题型管理本地题目包。"""

    def __init__(self, root: Path = QUESTION_BANK_DIR):
        self.root = root

    def ensure_layout(self) -> None:
        for section in ("listening", "reading", "writing", "speaking"):
            (self.root / section).mkdir(parents=True, exist_ok=True)

    def create_listening_draft(
        self,
        *,
        title: str,
        topic: str,
        task_type: str,
        reference_material: str,
        speaker_count: int,
        speed: str,
        voice: str,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_id = f"q_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        question_dir = self.root / "listening" / task_type / question_id
        question_dir.mkdir(parents=True, exist_ok=True)

        manifest = QuestionManifest(
            id=question_id,
            section="listening",
            task_type=task_type,
            title=title,
            topic=topic,
            reference_material=reference_material,
            parameters={
                "speaker_count": speaker_count,
                "speed": speed,
                "voice": voice,
                "play_count": 2,
            },
        )
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_listening_aufgabe_1(
        self,
        *,
        question_id: str,
        scenario: str,
        reference_material: str,
        difficulty: str,
        information_flow: str,
        speech_speed: str,
        speaker_voice_map: dict[str, str],
        generation: dict,
        audio_filename: str,
        audio_size_kb: float,
        segment_files: list[str],
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("listening", "aufgabe_1", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)

        transcript = generation["transcript"].strip()
        questions = generation["questions"]

        (question_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
        self._write_json(question_dir / "segments.json", generation["segments"])
        self._write_json(question_dir / "questions.json", questions)

        preview_markdown = self._build_preview_markdown(generation, speaker_voice_map)
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")

        manifest = QuestionManifest(
            id=question_id,
            section="listening",
            task_type="aufgabe_1",
            title=generation["title"].strip(),
            topic=generation["topic"].strip(),
            reference_material=reference_material,
            parameters={
                "scenario": scenario,
                "difficulty": difficulty,
                "information_flow": information_flow,
                "speech_speed": speech_speed,
                "speaker_voice_map": speaker_voice_map,
                "speaker_count": 2,
                "speaker_roles": generation["speaker_roles"],
                "relationship": generation["relationship"],
                "question_count": 8,
                "answer_mode": "short_text",
            },
            assets={
                "transcript": "transcript.txt",
                "segments": "segments.json",
                "questions": "questions.json",
                "preview": "preview.md",
                "audio": audio_filename,
                "audio_size_kb": audio_size_kb,
                "audio_segments": segment_files,
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_listening_aufgabe_2(
        self,
        *,
        question_id: str,
        topic_input: str,
        reference_material: str,
        difficulty: str,
        information_flow: str,
        statement_balance: str,
        speech_speed: str,
        speaker_voice_map: dict[str, str],
        generation: dict,
        audio_filename: str,
        audio_size_kb: float,
        segment_files: list[str],
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("listening", "aufgabe_2", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)

        transcript = generation["transcript"].strip()
        statements = generation["statements"]

        (question_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
        self._write_json(question_dir / "segments.json", generation["segments"])
        self._write_json(question_dir / "statements.json", statements)
        self._write_json(question_dir / "questions.json", statements)

        preview_markdown = self._build_aufgabe_2_preview_markdown(generation, speaker_voice_map)
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")

        manifest = QuestionManifest(
            id=question_id,
            section="listening",
            task_type="aufgabe_2",
            title=generation["title"].strip(),
            topic=generation["topic"].strip(),
            reference_material=reference_material,
            parameters={
                "topic_input": topic_input,
                "difficulty": difficulty,
                "information_flow": information_flow,
                "statement_balance": statement_balance,
                "speech_speed": speech_speed,
                "speaker_voice_map": speaker_voice_map,
                "speaker_count": 3,
                "speaker_roles": generation["speaker_roles"],
                "format_note": generation["format_note"],
                "question_count": 10,
                "answer_mode": "richtig_falsch",
            },
            assets={
                "transcript": "transcript.txt",
                "segments": "segments.json",
                "questions": "questions.json",
                "statements": "statements.json",
                "preview": "preview.md",
                "audio": audio_filename,
                "audio_size_kb": audio_size_kb,
                "audio_segments": segment_files,
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_listening_aufgabe_3(
        self,
        *,
        question_id: str,
        topic_input: str,
        expert_domain_input: str,
        reference_material: str,
        difficulty: str,
        question_focus_mix: str,
        multi_point_questions: int,
        speech_speed: str,
        speaker_voice_map: dict[str, str],
        generation: dict,
        audio_filename: str,
        audio_size_kb: float,
        segment_files: list[str],
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("listening", "aufgabe_3", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)

        transcript = generation["transcript"].strip()
        questions = generation["questions"]

        (question_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
        self._write_json(question_dir / "segments.json", generation["segments"])
        self._write_json(question_dir / "questions.json", questions)

        preview_markdown = self._build_aufgabe_3_preview_markdown(generation, speaker_voice_map)
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")

        manifest = QuestionManifest(
            id=question_id,
            section="listening",
            task_type="aufgabe_3",
            title=generation["title"].strip(),
            topic=generation["topic"].strip(),
            reference_material=reference_material,
            parameters={
                "topic_input": topic_input,
                "expert_domain_input": expert_domain_input,
                "difficulty": difficulty,
                "question_focus_mix": question_focus_mix,
                "multi_point_questions": multi_point_questions,
                "speech_speed": speech_speed,
                "speaker_voice_map": speaker_voice_map,
                "speaker_count": 2,
                "speaker_roles": generation["speaker_roles"],
                "expert_domain": generation["expert_domain"],
                "format_note": generation["format_note"],
                "question_count": 7,
                "answer_mode": "short_text",
                "play_count": 2,
            },
            assets={
                "transcript": "transcript.txt",
                "segments": "segments.json",
                "questions": "questions.json",
                "preview": "preview.md",
                "audio": audio_filename,
                "audio_size_kb": audio_size_kb,
                "audio_segments": segment_files,
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_reading_aufgabe_1(
        self,
        *,
        question_id: str,
        topic_input: str,
        reference_material: str,
        difficulty: str,
        offer_count: int,
        no_match_count: int,
        generation: dict,
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("reading", "aufgabe_1", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(question_dir / "texts.json", generation["offers"])
        self._write_json(question_dir / "profiles.json", generation["profiles"])
        self._write_json(question_dir / "questions.json", generation["answers"])
        preview_markdown = self._build_reading_aufgabe_1_preview_markdown(generation)
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")
        manifest = QuestionManifest(
            id=question_id,
            section="reading",
            task_type="aufgabe_1",
            title=generation["title"].strip(),
            topic=generation["topic"].strip(),
            reference_material=reference_material,
            parameters={
                "topic_input": topic_input,
                "difficulty": difficulty,
                "offer_count": offer_count,
                "profile_count": 10,
                "no_match_count": no_match_count,
                "question_count": 10,
                "answer_mode": "matching",
                "length_metadata": generation.get("length_metadata"),
                "example_offer_label": generation.get("example_offer_label"),
            },
            assets={
                "texts": "texts.json",
                "profiles": "profiles.json",
                "questions": "questions.json",
                "preview": "preview.md",
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_reading_aufgabe_2(
        self,
        *,
        question_id: str,
        topic_input: str,
        reference_material: str,
        difficulty: str,
        text_length: str,
        skill_focus: str,
        generation: dict,
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("reading", "aufgabe_2", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)
        (question_dir / "reading_text.txt").write_text(generation["reading_text"].strip(), encoding="utf-8")
        self._write_json(question_dir / "paragraphs.json", generation["paragraphs"])
        self._write_json(question_dir / "questions.json", generation["questions"])
        preview_markdown = self._build_reading_aufgabe_2_preview_markdown(generation)
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")
        manifest = QuestionManifest(
            id=question_id,
            section="reading",
            task_type="aufgabe_2",
            title=generation["title"].strip(),
            topic=generation["topic"].strip(),
            reference_material=reference_material,
            parameters={
                "topic_input": topic_input,
                "difficulty": difficulty,
                "text_length": text_length,
                "skill_focus": skill_focus,
                "question_count": 10,
                "answer_mode": "single_choice_abc",
                "length_metadata": generation.get("length_metadata"),
            },
            assets={
                "reading_text": "reading_text.txt",
                "paragraphs": "paragraphs.json",
                "questions": "questions.json",
                "preview": "preview.md",
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_reading_aufgabe_3(
        self,
        *,
        question_id: str,
        topic_input: str,
        reference_material: str,
        difficulty: str,
        judgement_balance: str,
        unsupported_items: str,
        generation: dict,
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("reading", "aufgabe_3", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)
        (question_dir / "reading_text.txt").write_text(generation["reading_text"].strip(), encoding="utf-8")
        self._write_json(question_dir / "paragraphs.json", generation["paragraphs"])
        self._write_json(question_dir / "statements.json", generation["statements"])
        self._write_json(question_dir / "questions.json", generation["statements"])
        preview_markdown = self._build_reading_aufgabe_3_preview_markdown(generation)
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")
        manifest = QuestionManifest(
            id=question_id,
            section="reading",
            task_type="aufgabe_3",
            title=generation["title"].strip(),
            topic=generation["topic"].strip(),
            reference_material=reference_material,
            parameters={
                "topic_input": topic_input,
                "difficulty": difficulty,
                "judgement_balance": judgement_balance,
                "unsupported_items": unsupported_items,
                "question_count": 10,
                "answer_mode": "ja_nein_not_given",
                "length_metadata": generation.get("length_metadata"),
            },
            assets={
                "reading_text": "reading_text.txt",
                "paragraphs": "paragraphs.json",
                "questions": "questions.json",
                "statements": "statements.json",
                "preview": "preview.md",
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_writing_aufgabe_1(
        self,
        *,
        question_id: str,
        topic_input: str,
        reference_material: str,
        difficulty: str,
        chart_count: int,
        chart_type_preference: str,
        argument_focus: str,
        country_comparison: str,
        generation: dict,
        chart_files: list[str],
        reference_image_files: list[str],
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("writing", "aufgabe_1", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(
            question_dir / "prompt.json",
            {
                "title": generation["title"],
                "topic": generation["topic"],
                "background": generation["background"],
                "task_prompt": generation["task_prompt"],
                "writing_instructions": generation["writing_instructions"],
                "image_usage_note": generation.get("image_usage_note", ""),
                "length_metadata": generation.get("length_metadata"),
            },
        )
        self._write_json(question_dir / "charts.json", generation["chart_specs"])

        relative_path = question_dir.relative_to(self.root)
        preview_markdown = self._build_writing_aufgabe_1_preview_markdown(
            generation,
            relative_path=str(relative_path),
            chart_files=chart_files,
        )
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")

        manifest = QuestionManifest(
            id=question_id,
            section="writing",
            task_type="aufgabe_1",
            title=generation["title"].strip(),
            topic=generation["topic"].strip(),
            reference_material=reference_material,
            parameters={
                "topic_input": topic_input,
                "difficulty": difficulty,
                "chart_count": chart_count,
                "chart_type_preference": chart_type_preference,
                "argument_focus": argument_focus,
                "country_comparison": country_comparison,
                "task_text_bytes": generation.get("length_metadata", {}).get("task_text_bytes"),
                "answer_mode": "essay",
            },
            assets={
                "prompt": "prompt.json",
                "charts": "charts.json",
                "chart_images": chart_files,
                "reference_images": reference_image_files,
                "preview": "preview.md",
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_speaking_test_set(
        self,
        *,
        question_id: str,
        title: str,
        topic_summary: str,
        tasks: list[dict],
        reference_material: str,
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        question_dir = self.get_question_dir("speaking", "test_set", question_id)
        question_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(question_dir / "tasks.json", tasks)

        for task in tasks:
            task_dir = question_dir / f"task_{task['number']}"
            task_dir.mkdir(parents=True, exist_ok=True)
            self._write_json(task_dir / "prompt.json", task)

        preview_markdown = self._build_speaking_test_set_preview_markdown(
            tasks,
            relative_path=str(question_dir.relative_to(self.root)),
        )
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")

        manifest = QuestionManifest(
            id=question_id,
            section="speaking",
            task_type="test_set",
            title=title,
            topic=topic_summary,
            reference_material=reference_material,
            parameters={
                "task_count": 7,
                "answer_mode": "spoken_response",
            },
            assets={
                "tasks": "tasks.json",
                "preview": "preview.md",
                "audio_files": [task.get("audio") for task in tasks if task.get("audio")],
                "chart_images": [
                    chart_file
                    for task in tasks
                    for chart_file in task.get("chart_files", [])
                ],
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def save_speaking_aufgabe(
        self,
        *,
        question_id: str,
        number: int,
        topic_input: str,
        reference_material: str,
        difficulty: str,
        generation: dict,
        chart_files: list[str],
        reference_image_files: list[str],
        reference_sources: dict | None = None,
    ) -> QuestionManifest:
        self.ensure_layout()
        task_type = f"aufgabe_{number}"
        question_dir = self.get_question_dir("speaking", task_type, question_id)
        question_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(question_dir / "prompt.json", generation)
        self._write_json(question_dir / "charts.json", generation.get("chart_specs", []))

        preview_markdown = self._build_speaking_aufgabe_preview_markdown(
            generation,
            relative_path=str(question_dir.relative_to(self.root)),
            chart_files=chart_files,
        )
        (question_dir / "preview.md").write_text(preview_markdown, encoding="utf-8")

        manifest = QuestionManifest(
            id=question_id,
            section="speaking",
            task_type=task_type,
            title=generation["title"].strip(),
            topic=topic_input,
            reference_material=reference_material,
            parameters={
                "number": number,
                "difficulty": difficulty,
                "task_type_label": generation["task_type"],
                "prep_time": generation["prep_time"],
                "speaking_time": generation["speaking_time"],
                "examiner_role": generation["examiner_role"],
                "voice": generation["voice"],
                "needs_chart": generation["needs_chart"],
                "answer_mode": "spoken_response",
            },
            assets={
                "prompt": "prompt.json",
                "charts": "charts.json",
                "chart_images": chart_files,
                "reference_images": reference_image_files,
                "audio": generation.get("audio"),
                "preview": "preview.md",
            },
        )
        self._write_reference_sources(question_dir, manifest, reference_sources)
        self._write_manifest(question_dir, manifest)
        return manifest

    def list_questions(self, section: str | None = None) -> list[dict]:
        self.ensure_layout()
        base = self.root / section if section else self.root
        manifests = []
        for manifest_path in sorted(base.glob("**/manifest.json"), reverse=True):
            if ".trash" in str(manifest_path):
                continue
            data = read_json(manifest_path)
            data["_path"] = str(manifest_path.parent.relative_to(self.root))
            manifests.append(data)
        return manifests

    def get_question(self, question_id: str) -> dict:
        self.ensure_layout()
        for manifest_path in self.root.glob("**/manifest.json"):
            if ".trash" in str(manifest_path):
                continue
            data = read_json(manifest_path)
            if data.get("id") == question_id:
                data["_path"] = str(manifest_path.parent.relative_to(self.root))
                return data
        raise KeyError(f"题目 {question_id} 不存在")

    @property
    def trash_dir(self) -> Path:
        return self.root / ".trash"

    def _resolve_inside(self, base: Path, relative_path: str, error_message: str) -> Path:
        if not relative_path:
            raise RuntimeError(error_message)
        return resolve_inside(base, relative_path, error_message)

    def _resolve_question_path(self, relative_path: str) -> Path:
        return self._resolve_inside(self.root, relative_path, "题目路径非法")

    def _resolve_trash_path(self, relative_path: str) -> Path:
        return self._resolve_inside(self.trash_dir, relative_path, "垃圾箱路径非法")

    def move_to_trash(self, relative_path: str) -> None:
        src = self._resolve_question_path(relative_path)
        if not src.exists():
            raise RuntimeError("题目不存在")
        normalized_path = src.relative_to(self.root.resolve()).as_posix()
        section = Path(normalized_path).parts[0] if Path(normalized_path).parts else ""
        trash_target = self._resolve_trash_path(normalized_path)
        trash_target.parent.mkdir(parents=True, exist_ok=True)
        trash_info = {
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "original_path": normalized_path,
            "section": section,
        }
        manifest = read_json(src / "manifest.json")
        trash_info["title"] = manifest.get("title", "")
        trash_info["task_type"] = manifest.get("task_type", "")
        trash_target.parent.mkdir(parents=True, exist_ok=True)
        if trash_target.exists():
            shutil.rmtree(str(trash_target))
        shutil.move(str(src), str(trash_target))
        self._write_json(trash_target / ".trash_info.json", trash_info)

    def restore_from_trash(self, trash_relative_path: str) -> None:
        src = self._resolve_trash_path(trash_relative_path)
        if not src.exists():
            raise RuntimeError("垃圾箱中未找到该题目")
        info_path = src / ".trash_info.json"
        if not info_path.exists():
            raise RuntimeError("垃圾箱信息丢失")
        trash_info = read_json(info_path)
        original_path = trash_info.get("original_path", "")
        if not original_path:
            raise RuntimeError("无法确定原始位置")
        target = self._resolve_question_path(original_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise RuntimeError("原始位置已有题目，请先处理冲突后再恢复")
        shutil.move(str(src), str(target))
        info_path = target / ".trash_info.json"
        if info_path.exists():
            info_path.unlink()

    def list_trash(self) -> list[dict]:
        self.cleanup_expired_trash()
        if not self.trash_dir.exists():
            return []
        items = []
        for info_path in sorted(self.trash_dir.glob("**/.trash_info.json"), reverse=True):
            info = read_json(info_path)
            info["_trash_path"] = str(info_path.parent.relative_to(self.trash_dir))
            items.append(info)
        return items

    def cleanup_expired_trash(self) -> None:
        if not self.trash_dir.exists():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_RETENTION_DAYS)
        for info_path in list(self.trash_dir.glob("**/.trash_info.json")):
            try:
                info = read_json(info_path)
                deleted_str = info.get("deleted_at", "")
                if not deleted_str:
                    continue
                deleted_at = datetime.fromisoformat(deleted_str)
                if deleted_at < cutoff:
                    shutil.rmtree(str(info_path.parent))
            except (OSError, ValueError, json.JSONDecodeError):
                pass

    def rename_question(self, relative_path: str, new_title: str) -> None:
        question_dir = self._resolve_question_path(relative_path)
        if not question_dir.exists():
            raise RuntimeError("题目不存在")
        manifest_path = question_dir / "manifest.json"
        manifest = read_json(manifest_path)
        manifest["title"] = new_title.strip()
        manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._write_json(manifest_path, manifest)

    def new_question_id(self) -> str:
        return f"q_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

    def get_question_dir(self, section: str, task_type: str, question_id: str) -> Path:
        return self.root / section / task_type / question_id

    def load_question_bundle(self, relative_path: str) -> dict:
        question_dir = self._resolve_question_path(relative_path)
        manifest_path = question_dir / "manifest.json"
        manifest = read_json(manifest_path)

        normalized_path = question_dir.relative_to(self.root.resolve()).as_posix()
        bundle = {"manifest": manifest, "path": normalized_path}
        for key in (
            "transcript",
            "segments",
            "questions",
            "statements",
            "texts",
            "profiles",
            "paragraphs",
            "reading_text",
            "prompt",
            "charts",
            "tasks",
            "reference_sources",
            "preview",
        ):
            asset = manifest.get("assets", {}).get(key)
            if not asset:
                continue
            asset_path = (question_dir / asset).resolve()
            try:
                asset_path.relative_to(question_dir.resolve())
            except ValueError as exc:
                raise RuntimeError("题目资源路径非法") from exc
            if asset_path.suffix == ".json":
                bundle[key] = read_json(asset_path)
            else:
                bundle[key] = asset_path.read_text(encoding="utf-8")
        return bundle

    def _write_manifest(self, question_dir: Path, manifest: QuestionManifest) -> None:
        manifest_path = question_dir / "manifest.json"
        self._write_json(manifest_path, asdict(manifest))

    def _write_json(self, path: Path, data: object) -> None:
        write_json_atomic(path, data)

    def _write_reference_sources(
        self,
        question_dir: Path,
        manifest: QuestionManifest,
        reference_sources: dict | None,
    ) -> None:
        if not reference_sources:
            return
        self._write_json(question_dir / "reference_sources.json", reference_sources)
        manifest.assets["reference_sources"] = "reference_sources.json"

    def _build_preview_markdown(self, generation: dict, speaker_voice_map: dict[str, str]) -> str:
        speaker_roles = generation["speaker_roles"]
        lines = [
            f"## Hörtext 1: {generation['title']}",
            "",
            f"**Thema**: {generation['topic']}",
            f"**Beziehung**: {generation['relationship']}",
            "",
            "### Sprecher",
            "",
            f"- **A**: {speaker_roles['A']} · Stimme: `{speaker_voice_map['A']}`",
            f"- **B**: {speaker_roles['B']} · Stimme: `{speaker_voice_map['B']}`",
            "",
            "### Transkript",
            "",
        ]

        for segment in generation["segments"]:
            speaker = segment["speaker_id"]
            pause = segment["pause_after_ms"]
            lines.append(f"**{speaker}**: {segment['text']}")
            lines.append("")
            lines.append(f"<small>Pause: {pause} ms · {segment['pause_reason']}</small>")
            lines.append("")

        lines.extend(["### Aufgaben 1-8", ""])
        for question in generation["questions"]:
            answers = "; ".join(question["answer"])
            variants = "; ".join(question["acceptable_variants"])
            lines.append(f"{question['number']}. **{question['prompt']}**")
            lines.append(f"   - Erwartete Antwort: {answers}")
            if variants:
                lines.append(f"   - Akzeptierte Varianten: {variants}")
            lines.append(f"   - Beleg: {question['evidence']}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _build_aufgabe_2_preview_markdown(
        self,
        generation: dict,
        speaker_voice_map: dict[str, str],
    ) -> str:
        speaker_roles = generation["speaker_roles"]
        metadata = generation.get("metadata", {})
        lines = [
            f"## Hörtext 2: {generation['title']}",
            "",
            f"**Thema**: {generation['topic']}",
            f"**Format**: {generation['format_note']}",
            "",
            "### Sprecher",
            "",
        ]

        for speaker_id in ("A", "B", "C"):
            lines.append(
                f"- **{speaker_id}**: {speaker_roles[speaker_id]} · "
                f"Stimme: `{speaker_voice_map[speaker_id]}`"
            )

        if metadata:
            lines.extend(
                [
                    "",
                    "### Längenprüfung",
                    "",
                    f"- UTF-8 bytes: `{metadata.get('transcript_bytes', 'n/a')}`",
                    f"- Status: `{metadata.get('length_status', 'n/a')}`",
                ]
            )

        lines.extend(["", "### Transkript", ""])
        for segment in generation["segments"]:
            speaker = segment["speaker_id"]
            pause = segment["pause_after_ms"]
            lines.append(f"**{speaker}**: {segment['text']}")
            lines.append("")
            lines.append(f"<small>Pause: {pause} ms · {segment['pause_reason']}</small>")
            lines.append("")

        lines.extend(["### Aufgaben 9-18: Richtig oder Falsch?", ""])
        for statement in generation["statements"]:
            lines.append(f"{statement['number']}. **{statement['statement']}**")
            lines.append(f"   - Lösung: **{statement['answer']}**")
            lines.append(f"   - Geprüfte Information: {statement['tested_information']}")
            lines.append(f"   - Beleg: {statement['evidence']}")
            lines.append(f"   - Distraktor: `{statement['distractor_type']}`")
            lines.append(f"   - Erklärung: {statement['distractor_explanation']}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _build_aufgabe_3_preview_markdown(
        self,
        generation: dict,
        speaker_voice_map: dict[str, str],
    ) -> str:
        speaker_roles = generation["speaker_roles"]
        metadata = generation.get("metadata", {})
        lines = [
            f"## Hörtext 3: {generation['title']}",
            "",
            f"**Thema**: {generation['topic']}",
            f"**Expertengebiet**: {generation['expert_domain']}",
            f"**Format**: {generation['format_note']}",
            "**Wiedergabe**: 2-mal",
            "",
            "### Sprecher",
            "",
        ]

        for speaker_id in ("A", "B"):
            lines.append(
                f"- **{speaker_id}**: {speaker_roles[speaker_id]} · "
                f"Stimme: `{speaker_voice_map[speaker_id]}`"
            )

        if metadata:
            lines.extend(
                [
                    "",
                    "### Längenprüfung",
                    "",
                    f"- UTF-8 bytes: `{metadata.get('transcript_bytes', 'n/a')}`",
                    f"- Status: `{metadata.get('length_status', 'n/a')}`",
                ]
            )

        lines.extend(["", "### Transkript", ""])
        for segment in generation["segments"]:
            speaker = segment["speaker_id"]
            pause = segment["pause_after_ms"]
            lines.append(f"**{speaker}**: {segment['text']}")
            lines.append("")
            lines.append(f"<small>Pause: {pause} ms · {segment['pause_reason']}</small>")
            lines.append("")

        lines.extend(["### Aufgaben 19-25", ""])
        for question in generation["questions"]:
            answers = "; ".join(question["answer"])
            variants = "; ".join(question["acceptable_variants"])
            lines.append(f"{question['number']}. **{question['prompt']}**")
            lines.append(f"   - Fokus: `{question['question_focus']}`")
            lines.append(f"   - Erwartete Antwort: {answers}")
            if variants:
                lines.append(f"   - Akzeptierte Varianten: {variants}")
            lines.append(f"   - Punkte: {question['required_points']}")
            lines.append(f"   - Beleg: {question['evidence']}")
            lines.append(f"   - Bewertung: {question['scoring_note']}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _build_reading_aufgabe_1_preview_markdown(self, generation: dict) -> str:
        example_label = generation.get("example_offer_label", "")
        lines = [
            f"## Lesetext 1: {generation['title']}",
            "",
            f"**Thema**: {generation['topic']}",
            "",
            "### Aufgabenstellung",
            "",
            generation["scenario"],
            "",
            "### Texte A-H",
            "",
            f"*示例短文（{example_label}）不在练习题中出现",
            "",
        ]
        metadata = generation.get("length_metadata", {})
        if metadata:
            lines.extend(
                [
                    "### Längenprüfung",
                    "",
                    f"- Ziel pro Text: `{metadata.get('target_per_offer_bytes', 'n/a')}` UTF-8 bytes",
                    f"- Status: `{metadata.get('status', 'n/a')}`",
                    "",
                ]
            )
            for label, item in metadata.get("offers", {}).items():
                lines.append(f"- {label}: `{item.get('bytes')}` bytes · `{item.get('status')}`")
            lines.append("")
        for offer in generation["offers"]:
            is_example = " ★（示例）" if offer["label"] == example_label else ""
            lines.append(f"#### {offer['label']}. {offer['heading']}{is_example}")
            lines.append(offer["text"])
            lines.append("")
        lines.extend(["### Personen 1-10", ""])
        for profile in generation["profiles"]:
            lines.append(f"{profile['number']}. {profile['need']}")
        lines.extend(["", "### Lösungen", ""])
        for answer in generation["answers"]:
            lines.append(f"{answer['number']}. **{answer['answer']}**")
            lines.append(f"   - Beleg: {answer['evidence']}")
            lines.append(f"   - Begründung: {answer['matching_reason']}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _build_reading_aufgabe_2_preview_markdown(self, generation: dict) -> str:
        lines = [
            f"## Lesetext 2: {generation['title']}",
            "",
            f"**Thema**: {generation['topic']}",
            "",
        ]
        metadata = generation.get("length_metadata", {})
        if metadata:
            lines.extend(
                [
                    "### Längenprüfung",
                    "",
                    f"- UTF-8 bytes: `{metadata.get('current_bytes', 'n/a')}`",
                    f"- Ziel: `{metadata.get('target_bytes', 'n/a')}`",
                    f"- Status: `{metadata.get('status', 'n/a')}`",
                    "",
                ]
            )
        lines.extend(
            [
                "### Lesetext",
                "",
                generation["reading_text"],
                "",
                "### Aufgaben 11-20",
                "",
            ]
        )
        for question in generation["questions"]:
            lines.append(f"{question['number']}. **{question['prompt']}**")
            for label in ("A", "B", "C"):
                lines.append(f"   - {label}: {question['options'][label]}")
            lines.append(f"   - Lösung: **{question['answer']}**")
            lines.append(f"   - Kompetenz: `{question['tested_skill']}`")
            lines.append(f"   - Beleg: {question['evidence']}")
            lines.append(f"   - Distraktoren: {question['distractor_explanation']}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _build_reading_aufgabe_3_preview_markdown(self, generation: dict) -> str:
        lines = [
            f"## Lesetext 3: {generation['title']}",
            "",
            f"**Thema**: {generation['topic']}",
            "",
        ]
        metadata = generation.get("length_metadata", {})
        if metadata:
            lines.extend(
                [
                    "### Längenprüfung",
                    "",
                    f"- UTF-8 bytes: `{metadata.get('current_bytes', 'n/a')}`",
                    f"- Ziel: `{metadata.get('target_bytes', 'n/a')}`",
                    f"- Status: `{metadata.get('status', 'n/a')}`",
                    "",
                ]
            )
        lines.extend(
            [
                "### Lesetext",
                "",
                generation["reading_text"],
                "",
                "### Aufgaben 21-30: Ja / Nein / Text sagt dazu nichts",
                "",
            ]
        )
        for statement in generation["statements"]:
            lines.append(f"{statement['number']}. **{statement['statement']}**")
            lines.append(f"   - Lösung: **{statement['answer']}**")
            lines.append(f"   - Typ: `{statement['judgement_type']}`")
            lines.append(f"   - Geprüfte Information: {statement['tested_information']}")
            lines.append(f"   - Beleg: {statement['evidence']}")
            lines.append(f"   - Erklärung: {statement['explanation']}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _build_writing_aufgabe_1_preview_markdown(
        self,
        generation: dict,
        *,
        relative_path: str,
        chart_files: list[str],
    ) -> str:
        lines = [
            f"## Schriftlicher Ausdruck: {generation['title']}",
            "",
            f"**Thema**: {generation['topic']}",
            "",
        ]
        lines.extend(
            [
                "### Thema",
                "",
                generation["background"],
                "",
                "### Schreiben Sie einen Text zum folgenden Thema",
                "",
                f"**{generation['task_prompt']}**",
                "",
                "### Bearbeiten Sie dabei die folgenden Punkte",
                "",
            ]
        )
        for instruction in generation["writing_instructions"]:
            lines.append(f"- {instruction}")
        lines.append("")

        for index, chart_file in enumerate(chart_files, start=1):
            lines.extend(
                [
                    f"### Grafik {index}",
                    "",
                    f'<img src="/question-bank/{relative_path}/{chart_file}" alt="Grafik {index}" class="preview-image">',
                    "",
                ]
            )

        return "\n".join(lines).strip() + "\n"

    def _build_speaking_test_set_preview_markdown(self, tasks: list[dict], *, relative_path: str) -> str:
        lines = [
            "## Mündlicher Ausdruck: Test-Set",
            "",
            "Diese Vorschau enthält alle sieben Aufgaben mit Situation, Antwortpunkten, Einleitungsaudio und optionalen Grafiken.",
            "",
        ]
        for task in tasks:
            number = task["number"]
            lines.extend(
                [
                    f"### Aufgabe {number}: {task['task_type']}",
                    "",
                    f"**Vorbereitungszeit**: {task['prep_time']}  ",
                    f"**Sprechzeit**: {task['speaking_time']}  ",
                    f"**Gesprächspartner/in**: {task['examiner_role']} · Stimme: `{task['voice']}`",
                    "",
                    "#### Situation",
                    "",
                    task["scenario"],
                    "",
                    "#### Ihre Aufgabe",
                    "",
                ]
            )
            for point in task["prompt_points"]:
                lines.append(f"- {point}")
            lines.extend(
                [
                    "",
                    "#### Gesprächsimpuls",
                    "",
                    f"> {task['examiner_intro']}",
                    "",
                ]
            )
            if task.get("audio"):
                lines.extend(
                    [
                        f'<audio controls src="/question-bank/{relative_path}/{task["audio"]}"></audio>',
                        "",
                    ]
                )
            for index, chart_file in enumerate(task.get("chart_files", []), start=1):
                lines.extend(
                    [
                        f"#### Grafik {index}",
                        "",
                        f'<img src="/question-bank/{relative_path}/{chart_file}" alt="Aufgabe {number} Grafik {index}" class="preview-image">',
                        "",
                    ]
                )
        return "\n".join(lines).strip() + "\n"

    def _build_speaking_aufgabe_preview_markdown(
        self,
        generation: dict,
        *,
        relative_path: str,
        chart_files: list[str],
    ) -> str:
        number = generation["number"]
        lines = [
            f"## Mündlicher Ausdruck Aufgabe {number}",
            "",
            f"**题型**: {generation['task_type']}  ",
            f"**Vorbereitungszeit**: {generation['prep_time']}  ",
            f"**Sprechzeit**: {generation['speaking_time']}  ",
            f"**Gesprächspartner/in**: {generation['examiner_role']} · Stimme: `{generation['voice']}`",
            "",
            "### Situation",
            "",
            generation["scenario"],
            "",
            "### Ihre Aufgabe",
            "",
        ]
        for point in generation["prompt_points"]:
            lines.append(f"- {point}")
        lines.extend(
            [
                "",
                "### Gesprächsimpuls",
                "",
                f"> {generation['examiner_intro']}",
                "",
            ]
        )
        if generation.get("audio"):
            lines.extend(
                [
                    f'<audio controls src="/question-bank/{relative_path}/{generation["audio"]}"></audio>',
                    "",
                ]
            )
        for index, chart_file in enumerate(chart_files, start=1):
            lines.extend(
                [
                    f"### Grafik {index}",
                    "",
                    f'<img src="/question-bank/{relative_path}/{chart_file}" alt="Aufgabe {number} Grafik {index}" class="preview-image">',
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"
