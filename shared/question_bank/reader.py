"""Read-only access to generated question packages."""

from __future__ import annotations

from pathlib import Path

from shared.file_io.atomic_json import read_json
from shared.file_io.path_guard import resolve_inside


class QuestionBankReader:
    """Read question manifests and bundles without exposing write operations."""

    def __init__(self, root: Path):
        self.root = root

    def list_questions(self, section: str | None = None) -> list[dict]:
        base = self.root / section if section else self.root
        if not base.exists():
            return []
        manifests = []
        for manifest_path in sorted(base.glob("**/manifest.json"), reverse=True):
            if ".trash" in manifest_path.parts:
                continue
            data = read_json(manifest_path)
            if not isinstance(data, dict):
                continue
            data["_path"] = str(manifest_path.parent.relative_to(self.root))
            manifests.append(data)
        return manifests

    def find_by_id(self, question_id: str) -> dict | None:
        for question in self.list_questions():
            if question.get("id") == question_id:
                return question
        return None

    def load_question_bundle(self, relative_path: str) -> dict:
        question_dir = resolve_inside(self.root, relative_path, "题目路径非法")
        manifest_path = question_dir / "manifest.json"
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict):
            raise RuntimeError("题目 manifest 格式非法")

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
            asset_path = resolve_inside(question_dir, asset, "题目资源路径非法")
            if asset_path.suffix == ".json":
                bundle[key] = read_json(asset_path)
            else:
                bundle[key] = asset_path.read_text(encoding="utf-8")
        return bundle
