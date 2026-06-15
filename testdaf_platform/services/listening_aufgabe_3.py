"""TestDaF 听力 Aufgabe 3 生成服务。"""

import json
import re
from dataclasses import dataclass

import dashscope

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL
from testdaf_platform.services.text_generation import TextGenerationClient

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

MIN_TRANSCRIPT_BYTES = 4050
MAX_TRANSCRIPT_BYTES = 4450
TARGET_TRANSCRIPT_BYTES = 4243
HARD_MIN_TRANSCRIPT_BYTES = 3850
HARD_MAX_TRANSCRIPT_BYTES = 4650
MAX_LENGTH_REPAIR_ATTEMPTS = 3
MAX_STRUCTURE_RETRY_ATTEMPTS = 2
ALLOWED_SPEAKERS = {"A", "B"}
ALLOWED_PAUSES = {200, 350, 500, 750, 1000}


class Aufgabe3TranscriptLengthError(RuntimeError):
    """听力第三题原文长度不满足考试材料篇幅要求。"""

    def __init__(self, current_bytes: int):
        self.current_bytes = current_bytes
        super().__init__(
            f"听力第三题原文 UTF-8 长度应在 {MIN_TRANSCRIPT_BYTES}-{MAX_TRANSCRIPT_BYTES} 字节之间，"
            f"当前为 {current_bytes} 字节"
        )


@dataclass(frozen=True)
class ListeningAufgabe3Input:
    topic: str
    expert_domain: str
    reference_material: str
    difficulty: str
    question_focus_mix: str
    multi_point_questions: int


class ListeningAufgabe3Generator:
    """生成 TestDaF 听力第三题的结构化物料。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model
        self.client = TextGenerationClient(model=model)

    def generate(self, api_key: str, data: ListeningAufgabe3Input) -> dict:
        last_error: RuntimeError | None = None
        for structure_attempt in range(MAX_STRUCTURE_RETRY_ATTEMPTS + 1):
            payload = self._normalize_payload(self._generate_initial_payload(api_key, data))
            try:
                for attempt in range(MAX_LENGTH_REPAIR_ATTEMPTS + 1):
                    self._validate_structure(payload)
                    payload = self._normalize_payload(payload)
                    current_bytes = self._transcript_bytes(payload)

                    if MIN_TRANSCRIPT_BYTES <= current_bytes <= MAX_TRANSCRIPT_BYTES:
                        return self._with_length_metadata(payload, "ideal")

                    if attempt >= MAX_LENGTH_REPAIR_ATTEMPTS:
                        if HARD_MIN_TRANSCRIPT_BYTES <= current_bytes <= HARD_MAX_TRANSCRIPT_BYTES:
                            return self._with_length_metadata(payload, "accepted_with_warning")
                        raise Aufgabe3TranscriptLengthError(current_bytes)

                    if current_bytes < MIN_TRANSCRIPT_BYTES:
                        payload = self._expand_segments(
                            api_key=api_key,
                            data=data,
                            payload=payload,
                            current_bytes=current_bytes,
                            attempt=attempt + 1,
                        )
                    else:
                        payload = self._compress_segments(
                            api_key=api_key,
                            data=data,
                            payload=payload,
                            current_bytes=current_bytes,
                            attempt=attempt + 1,
                        )
            except RuntimeError as exc:
                last_error = exc
                if structure_attempt >= MAX_STRUCTURE_RETRY_ATTEMPTS or not self._should_regenerate(exc):
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("听力第三题生成失败：超过最大篇幅修复次数")

    def _should_regenerate(self, error: RuntimeError) -> bool:
        message = str(error)
        return "segments 至少需要" in message or "生成结果缺少字段" in message

    def _generate_initial_payload(self, api_key: str, data: ListeningAufgabe3Input) -> dict:
        content = self.client.generate_text(
            api_key=api_key,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(data)},
            ],
            max_tokens=8500,
        )

        return self._parse_json(content)

    def _expand_segments(
        self,
        *,
        api_key: str,
        data: ListeningAufgabe3Input,
        payload: dict,
        current_bytes: int,
        attempt: int,
    ) -> dict:
        missing_bytes = TARGET_TRANSCRIPT_BYTES - current_bytes
        content = self.client.generate_text(
            api_key=api_key,
            messages=[
                {"role": "system", "content": self._segment_expansion_system_prompt()},
                {
                    "role": "user",
                    "content": self._segment_expansion_user_prompt(
                        data=data,
                        payload=payload,
                        current_bytes=current_bytes,
                        missing_bytes=missing_bytes,
                        attempt=attempt,
                    ),
                },
            ],
            max_tokens=3000,
        )

        repair = self._parse_json(content)
        new_segments = self._extract_repair_segments(repair)
        insert_after = int(repair.get("insert_after_index", max(len(payload["segments"]) - 1, 1)))
        return self._insert_segments(payload, new_segments, insert_after)

    def _compress_segments(
        self,
        *,
        api_key: str,
        data: ListeningAufgabe3Input,
        payload: dict,
        current_bytes: int,
        attempt: int,
    ) -> dict:
        excess_bytes = current_bytes - TARGET_TRANSCRIPT_BYTES
        candidates = self._compression_candidates(payload)
        content = self.client.generate_text(
            api_key=api_key,
            messages=[
                {"role": "system", "content": self._segment_compression_system_prompt()},
                {
                    "role": "user",
                    "content": self._segment_compression_user_prompt(
                        data=data,
                        payload=payload,
                        candidates=candidates,
                        current_bytes=current_bytes,
                        excess_bytes=excess_bytes,
                        attempt=attempt,
                    ),
                },
            ],
            max_tokens=3000,
        )

        repair = self._parse_json(content)
        replacements = self._extract_repair_segments(repair)
        return self._replace_segments(payload, replacements)

    def _system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 出题专家，负责生成 TestDaF 听力第三题 Hörtext 3 的完整结构化物料。"
            "Hörtext 3 通常是主持人与一位专家的一对一学术、科普或专业知识访谈，播放两遍，共 7 道简短回答题，题号为 19-25。"
            "第三题不同于第二题：第二题考查 Richtig/Falsch 判断，第三题考查考生从高信息密度解释中提取原因、机制、比较、后果、用途、条件或建议。"
            "访谈必须有两个说话人：A 是主持人，B 是专家。主持人负责提出精准问题和转接；专家负责系统解释、举例、比较和给出专业建议。"
            "语言应比 Aufgabe 1 更学术、更解释型，也不能像 Aufgabe 2 那样围绕正误陈述设置观点归属干扰。"
            "用词、句式、说话方式和语气必须同时符合说话人身份、专家领域、学术访谈场景、具体主题以及老师指定的难度。"
            "standard 难度应符合 B2-C1；easy 应减少嵌套句和术语密度；hard 可以增加因果链、比较结构、抽象名词和限定条件。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外的任何文字。"
            "输出顶层字段必须包含 title、topic、expert_domain、speaker_roles、format_note、transcript、segments、questions。"
            "transcript 必须是自然德语专家访谈，UTF-8 byte length 目标约 4243，允许范围 4050-4450。"
            "transcript 必须能由 segments 按顺序还原为 A:/B: 标注的完整访谈。"
            "每个 segment 只能包含一个说话人的连续发言，并包含 index、speaker_id、speaker_role、text、pause_after_ms、pause_reason。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "pause_reason 用英文短标签，例如 host_question、expert_explanation、important_information、comparison、topic_shift、summary。"
            "questions 必须恰好 7 个元素，number 必须为 19-25。"
            "每个 question 必须包含 number、prompt、question_focus、required_points、answer、acceptable_variants、evidence、scoring_note。"
            "prompt 必须是德语问题，answer 必须是关键词或短语，不要写成长句。"
            "required_points 可以为 1 或 2；多信息点题不宜过多，但必须清楚可评分。"
        )

    def _user_prompt(self, data: ListeningAufgabe3Input) -> str:
        difficulty_instruction = {
            "easy": "偏简单：术语解释更清楚，句子较短，因果链不超过两步。",
            "hard": "偏困难：可加入更密集的因果解释、比较、限制条件和少量专业术语，但仍需可听懂。",
        }.get(data.difficulty, "标准 B2-C1：解释清楚但信息密度较高，适合 TestDaF 第三题。")
        focus_instruction = (
            "题目应覆盖原因、机制、比较、后果、用途和建议等功能。"
            if data.question_focus_mix == "balanced"
            else "题目功能可根据主题自然分布，但必须避免全部只考事实复述。"
        )
        reference = data.reference_material or "无额外参考素材。"
        return (
            "请根据以下老师输入生成 TestDaF Hörverstehen Hörtext 3 的完整结构化题目物料。\n\n"
            "老师输入：\n"
            f"- 知识型主题：{data.topic}\n"
            f"- 专家领域：{data.expert_domain}\n"
            f"- 参考素材：{reference}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 题目功能组合：{data.question_focus_mix}\n"
            f"- 多信息点题数量：{data.multi_point_questions}\n\n"
            f"难度语言规则：{difficulty_instruction}\n"
            "请特别注意：用词、说话方式、术语密度、句子长度、解释层次和信息密度都要匹配专家身份、学术访谈场景和难度。\n\n"
            f"题目功能规则：{focus_instruction}\n"
            f"请生成约 {data.multi_point_questions} 道 required_points=2 的题目，其余题目 required_points=1。\n\n"
            "篇幅要求：\n"
            "- transcript 的 UTF-8 byte length 目标约 4243。\n"
            "- 允许范围为 4050-4450。\n"
            "- 如果内容不足，请自然增加机制解释、研究发现、比较、具体例子、限制条件或专家建议。\n"
            "- 不要为了凑长度重复无意义内容。\n\n"
            "访谈结构要求：\n"
            "- A 必须是主持人，负责提出清楚的问题、追问和总结。\n"
            "- B 必须是一位明确领域的专家，回答应体现专业性和解释性。\n"
            "- 内容应像真实科普/学术访谈，不要像课堂讲稿、百科词条或考试说明。\n"
            "- 每 1-2 个问答段应自然支撑一道或两道短答题。\n\n"
            "停顿要求：\n"
            "- 每个 segment 后必须给出 pause_after_ms。\n"
            "- 普通接话使用 200 或 350。\n"
            "- 重要机制、结论、比较或建议后使用 500 或 750。\n"
            "- 话题转换、主持人总结或段落结束可使用 750 或 1000。\n"
            "- 不要依赖 SSML、特殊占位符或括号说明来控制停顿。\n\n"
            "请严格输出以下 JSON 结构：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "topic": "主题标签或主题短语",\n'
            '  "expert_domain": "专家领域",\n'
            '  "speaker_roles": {\n'
            '    "A": "Moderator/in",\n'
            '    "B": "专家身份"\n'
            "  },\n"
            '  "format_note": "wissenschaftliches Experteninterview",\n'
            '  "transcript": "A: ...\\nB: ...",\n'
            '  "segments": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "speaker_id": "A",\n'
            '      "speaker_role": "Moderator/in",\n'
            '      "text": "德语发言文本",\n'
            '      "pause_after_ms": 350,\n'
            '      "pause_reason": "host_question"\n'
            "    }\n"
            "  ],\n"
            '  "questions": [\n'
            "    {\n"
            '      "number": 19,\n'
            '      "prompt": "德语问题",\n'
            '      "question_focus": "cause/mechanism/comparison/consequence/use/recommendation",\n'
            '      "required_points": 1,\n'
            '      "answer": ["标准答案"],\n'
            '      "acceptable_variants": ["可接受变体"],\n'
            '      "evidence": "原文依据",\n'
            '      "scoring_note": "评分说明"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _segment_expansion_system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 专家访谈扩写专家。当前 Hörtext 3 访谈偏短，"
            "你只负责生成可插入到现有访谈中的新增 segments。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "不要返回完整题目 JSON，只返回 insert_after_index 和 segments。"
            "新增内容必须符合一对一专家访谈语境，补充机制解释、比较、研究发现、限制条件、例子或建议。"
            "新增内容的用词、说话方式、术语密度和解释层次必须符合角色身份、专家领域、场景和难度。"
            "不要改变已有 7 道短答题的答案，不要引入与原访谈冲突的新事实。"
            "speaker_id 只能是 A 或 B；A 是主持人，B 是专家。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "输出格式为：{\"insert_after_index\": 5, \"segments\": [...]}"
        )

    def _segment_expansion_user_prompt(
        self,
        *,
        data: ListeningAufgabe3Input,
        payload: dict,
        current_bytes: int,
        missing_bytes: int,
        attempt: int,
    ) -> str:
        return (
            f"这是第 {attempt} 次第三题局部扩写。\n"
            f"当前 transcript UTF-8 byte length：{current_bytes}\n"
            f"目标 byte length：约 {TARGET_TRANSCRIPT_BYTES}\n"
            f"估计还需要补充约 {max(missing_bytes, 160)} bytes。\n\n"
            "原始老师输入：\n"
            f"- 知识型主题：{data.topic}\n"
            f"- 专家领域：{data.expert_domain}\n"
            f"- 参考素材：{data.reference_material or '无额外参考素材。'}\n"
            f"- 难度：{data.difficulty}\n\n"
            "当前题目 JSON 摘要：\n"
            f"{json.dumps(self._repair_context(payload), ensure_ascii=False, indent=2)}\n\n"
            "请只输出新增片段 JSON：\n"
            "{\n"
            '  "insert_after_index": 5,\n'
            '  "segments": [\n'
            "    {\n"
            '      "speaker_id": "B",\n'
            '      "speaker_role": "专家身份",\n'
            '      "text": "新增德语发言",\n'
            '      "pause_after_ms": 500,\n'
            '      "pause_reason": "expert_explanation"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _segment_compression_system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 专家访谈压缩专家。当前 Hörtext 3 访谈偏长，"
            "你只负责压缩指定 segments，不要重写完整 JSON。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "必须保留短答题 evidence 所需信息、speaker_id 和自然德语表达。"
            "压缩后仍要保持专家身份、学术访谈语气、解释逻辑和难度匹配。"
            "优先删除冗余铺垫、重复解释和非必要例子。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "输出格式为：{\"segments\": [{\"index\": 4, \"text\": \"...\", \"pause_after_ms\": 350, \"pause_reason\": \"...\"}]}"
        )

    def _segment_compression_user_prompt(
        self,
        *,
        data: ListeningAufgabe3Input,
        payload: dict,
        candidates: list[dict],
        current_bytes: int,
        excess_bytes: int,
        attempt: int,
    ) -> str:
        return (
            f"这是第 {attempt} 次第三题局部压缩。\n"
            f"当前 transcript UTF-8 byte length：{current_bytes}\n"
            f"目标 byte length：约 {TARGET_TRANSCRIPT_BYTES}\n"
            f"估计需要减少约 {max(excess_bytes, 160)} bytes。\n\n"
            "原始老师输入：\n"
            f"- 知识型主题：{data.topic}\n"
            f"- 专家领域：{data.expert_domain}\n"
            f"- 参考素材：{data.reference_material or '无额外参考素材。'}\n"
            f"- 难度：{data.difficulty}\n\n"
            "题目 evidence 摘要，压缩时必须保留这些答案依据：\n"
            f"{json.dumps([q.get('evidence', '') for q in payload['questions']], ensure_ascii=False, indent=2)}\n\n"
            "请只压缩以下候选 segments，并返回压缩后的 replacements：\n"
            f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n\n"
            "输出格式：\n"
            "{\n"
            '  "segments": [\n'
            "    {\n"
            '      "index": 4,\n'
            '      "text": "压缩后的德语发言",\n'
            '      "pause_after_ms": 350,\n'
            '      "pause_reason": "expert_explanation"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _parse_json(self, content: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                raise RuntimeError("无法从 API 响应中解析 JSON")
            return json.loads(match.group(0))

    def _validate_structure(self, payload: dict) -> None:
        required_keys = {
            "title",
            "topic",
            "expert_domain",
            "speaker_roles",
            "format_note",
            "transcript",
            "segments",
            "questions",
        }
        missing = required_keys - payload.keys()
        if missing:
            raise RuntimeError(f"听力第三题生成结果缺少字段：{', '.join(sorted(missing))}")

        speaker_roles = payload["speaker_roles"]
        if not isinstance(speaker_roles, dict) or ALLOWED_SPEAKERS - speaker_roles.keys():
            raise RuntimeError("speaker_roles 必须是包含 A、B 的对象")

        segments = payload["segments"]
        if not isinstance(segments, list) or len(segments) < 12:
            raise RuntimeError("听力第三题 segments 至少需要 12 段，以支持专家访谈音频合成")

        seen_speakers = set()
        for index, segment in enumerate(segments, start=1):
            if segment.get("index") != index:
                segment["index"] = index
            for key in ("speaker_id", "speaker_role", "text", "pause_after_ms", "pause_reason"):
                if key not in segment:
                    raise RuntimeError(f"第 {index} 段缺少字段：{key}")
            if segment["speaker_id"] not in ALLOWED_SPEAKERS:
                raise RuntimeError(f"第 {index} 段 speaker_id 必须是 A 或 B")
            if int(segment["pause_after_ms"]) not in ALLOWED_PAUSES:
                raise RuntimeError(f"第 {index} 段 pause_after_ms 不在允许档位中")
            seen_speakers.add(segment["speaker_id"])

        if seen_speakers != ALLOWED_SPEAKERS:
            raise RuntimeError("segments 必须同时包含 A 和 B 两个说话人")

        questions = payload["questions"]
        if not isinstance(questions, list) or len(questions) != 7:
            raise RuntimeError("听力第三题必须生成 7 道短答题")

        for index, question in enumerate(questions, start=19):
            if question.get("number") != index:
                question["number"] = index
            for key in (
                "prompt",
                "question_focus",
                "required_points",
                "answer",
                "acceptable_variants",
                "evidence",
                "scoring_note",
            ):
                if key not in question:
                    raise RuntimeError(f"第 {index} 题缺少字段：{key}")
            if int(question["required_points"]) not in {1, 2}:
                raise RuntimeError(f"第 {index} 题 required_points 必须是 1 或 2")

    def _normalize_payload(self, payload: dict) -> dict:
        self._normalize_segments(payload)
        payload["transcript"] = self._rebuild_transcript(payload.get("segments", []))
        return payload

    def _normalize_segments(self, payload: dict) -> None:
        speaker_roles = payload.get("speaker_roles", {})
        for index, segment in enumerate(payload.get("segments", []), start=1):
            segment["index"] = index
            speaker_id = segment.get("speaker_id")
            if speaker_id in speaker_roles:
                segment["speaker_role"] = segment.get("speaker_role") or speaker_roles[speaker_id]
            segment["text"] = str(segment.get("text", "")).strip()
            segment["pause_after_ms"] = int(segment.get("pause_after_ms", 350))
            segment["pause_reason"] = segment.get("pause_reason") or "expert_explanation"

    def _rebuild_transcript(self, segments: list[dict]) -> str:
        lines = []
        for segment in segments:
            speaker_id = segment.get("speaker_id", "")
            text = str(segment.get("text", "")).strip()
            lines.append(f"{speaker_id}: {text}")
        return "\n".join(lines)

    def _transcript_bytes(self, payload: dict) -> int:
        return len(payload["transcript"].encode("utf-8"))

    def _with_length_metadata(self, payload: dict, status: str) -> dict:
        metadata = payload.setdefault("metadata", {})
        metadata["transcript_bytes"] = self._transcript_bytes(payload)
        metadata["length_status"] = status
        metadata["ideal_byte_range"] = [MIN_TRANSCRIPT_BYTES, MAX_TRANSCRIPT_BYTES]
        metadata["hard_byte_range"] = [HARD_MIN_TRANSCRIPT_BYTES, HARD_MAX_TRANSCRIPT_BYTES]
        return payload

    def _repair_context(self, payload: dict) -> dict:
        normalized = self._normalize_payload(payload.copy())
        return {
            "title": payload.get("title"),
            "topic": payload.get("topic"),
            "expert_domain": payload.get("expert_domain"),
            "speaker_roles": payload.get("speaker_roles"),
            "format_note": payload.get("format_note"),
            "transcript_bytes": self._transcript_bytes(normalized),
            "segments": payload.get("segments", []),
            "questions": payload.get("questions", []),
        }

    def _extract_repair_segments(self, repair: dict | list) -> list[dict]:
        if isinstance(repair, list):
            segments = repair
        else:
            segments = repair.get("segments", [])
        if not isinstance(segments, list) or not segments:
            raise RuntimeError("LLM 修复结果未返回有效 segments")
        return segments

    def _insert_segments(self, payload: dict, new_segments: list[dict], insert_after: int) -> dict:
        speaker_roles = payload["speaker_roles"]
        normalized_new_segments = []
        for segment in new_segments:
            speaker_id = segment.get("speaker_id")
            if speaker_id not in ALLOWED_SPEAKERS:
                raise RuntimeError("扩写片段 speaker_id 必须是 A 或 B")
            normalized_new_segments.append(
                {
                    "speaker_id": speaker_id,
                    "speaker_role": segment.get("speaker_role") or speaker_roles[speaker_id],
                    "text": str(segment.get("text", "")).strip(),
                    "pause_after_ms": int(segment.get("pause_after_ms", 350)),
                    "pause_reason": segment.get("pause_reason") or "expert_explanation",
                }
            )

        segments = payload["segments"]
        insert_at = max(0, min(insert_after, len(segments)))
        payload["segments"] = segments[:insert_at] + normalized_new_segments + segments[insert_at:]
        return self._normalize_payload(payload)

    def _replace_segments(self, payload: dict, replacements: list[dict]) -> dict:
        by_index = {int(segment["index"]): segment for segment in replacements if "index" in segment}
        for segment in payload["segments"]:
            replacement = by_index.get(int(segment["index"]))
            if not replacement:
                continue
            if "text" in replacement:
                segment["text"] = str(replacement["text"]).strip()
            if "pause_after_ms" in replacement:
                segment["pause_after_ms"] = int(replacement["pause_after_ms"])
            if "pause_reason" in replacement:
                segment["pause_reason"] = replacement["pause_reason"]
        return self._normalize_payload(payload)

    def _compression_candidates(self, payload: dict) -> list[dict]:
        evidence_texts = [str(question.get("evidence", "")) for question in payload["questions"]]
        candidates = []
        for segment in payload["segments"]:
            text = segment["text"]
            is_evidence = any(evidence and evidence in text for evidence in evidence_texts)
            candidates.append(
                {
                    "index": segment["index"],
                    "speaker_id": segment["speaker_id"],
                    "speaker_role": segment["speaker_role"],
                    "text": text,
                    "pause_after_ms": segment["pause_after_ms"],
                    "pause_reason": segment["pause_reason"],
                    "is_evidence_segment": is_evidence,
                    "utf8_bytes": len(text.encode("utf-8")),
                }
            )

        non_evidence = [item for item in candidates if not item["is_evidence_segment"]]
        pool = non_evidence or candidates
        return sorted(pool, key=lambda item: item["utf8_bytes"], reverse=True)[:5]
