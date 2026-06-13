"""TestDaF 听力 Aufgabe 2 生成服务。"""

import json
import re
from dataclasses import dataclass

import dashscope
from dashscope import Generation

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

MIN_TRANSCRIPT_BYTES = 4400
MAX_TRANSCRIPT_BYTES = 4850
TARGET_TRANSCRIPT_BYTES = 4623
HARD_MIN_TRANSCRIPT_BYTES = 4200
HARD_MAX_TRANSCRIPT_BYTES = 5050
MAX_LENGTH_REPAIR_ATTEMPTS = 3
ALLOWED_SPEAKERS = {"A", "B", "C"}
ALLOWED_PAUSES = {200, 350, 500, 750, 1000}
VALID_ANSWERS = {"Richtig", "Falsch"}


class Aufgabe2TranscriptLengthError(RuntimeError):
    """听力第二题原文长度不满足考试材料篇幅要求。"""

    def __init__(self, current_bytes: int):
        self.current_bytes = current_bytes
        super().__init__(
            f"听力第二题原文 UTF-8 长度应在 {MIN_TRANSCRIPT_BYTES}-{MAX_TRANSCRIPT_BYTES} 字节之间，"
            f"当前为 {current_bytes} 字节"
        )


@dataclass(frozen=True)
class ListeningAufgabe2Input:
    topic: str
    reference_material: str
    difficulty: str
    information_flow: str
    statement_balance: str


class ListeningAufgabe2Generator:
    """生成 TestDaF 听力第二题的结构化物料。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model

    def generate(self, api_key: str, data: ListeningAufgabe2Input) -> dict:
        payload = self._normalize_payload(self._generate_initial_payload(api_key, data))

        for attempt in range(MAX_LENGTH_REPAIR_ATTEMPTS + 1):
            self._validate_structure(payload)
            payload = self._normalize_payload(payload)
            current_bytes = self._transcript_bytes(payload)

            if MIN_TRANSCRIPT_BYTES <= current_bytes <= MAX_TRANSCRIPT_BYTES:
                return self._with_length_metadata(payload, "ideal")

            if attempt >= MAX_LENGTH_REPAIR_ATTEMPTS:
                if HARD_MIN_TRANSCRIPT_BYTES <= current_bytes <= HARD_MAX_TRANSCRIPT_BYTES:
                    return self._with_length_metadata(payload, "accepted_with_warning")
                raise Aufgabe2TranscriptLengthError(current_bytes)

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

        raise RuntimeError("听力第二题生成失败：超过最大篇幅修复次数")

    def _generate_initial_payload(self, api_key: str, data: ListeningAufgabe2Input) -> dict:
        resp = Generation.call(
            model=self.model,
            api_key=api_key,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(data)},
            ],
            max_tokens=9000,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

        content = resp.output.text
        if not content:
            raise RuntimeError("API 未返回听力第二题内容")

        return self._parse_json(content)

    def _expand_segments(
        self,
        *,
        api_key: str,
        data: ListeningAufgabe2Input,
        payload: dict,
        current_bytes: int,
        attempt: int,
    ) -> dict:
        missing_bytes = TARGET_TRANSCRIPT_BYTES - current_bytes
        resp = Generation.call(
            model=self.model,
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

        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

        content = resp.output.text
        if not content:
            raise RuntimeError("API 未返回第二题扩写片段")

        repair = self._parse_json(content)
        new_segments = self._extract_repair_segments(repair)
        insert_after = int(repair.get("insert_after_index", max(len(payload["segments"]) - 1, 1)))
        return self._insert_segments(payload, new_segments, insert_after)

    def _compress_segments(
        self,
        *,
        api_key: str,
        data: ListeningAufgabe2Input,
        payload: dict,
        current_bytes: int,
        attempt: int,
    ) -> dict:
        excess_bytes = current_bytes - TARGET_TRANSCRIPT_BYTES
        candidates = self._compression_candidates(payload)
        resp = Generation.call(
            model=self.model,
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

        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

        content = resp.output.text
        if not content:
            raise RuntimeError("API 未返回第二题压缩片段")

        repair = self._parse_json(content)
        replacements = self._extract_repair_segments(repair)
        return self._replace_segments(payload, replacements)

    def _system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 出题专家，负责生成 TestDaF 听力第二题 Hörtext 2 的完整结构化物料。"
            "TestDaF 是面向准备进入德国高校学习者的德语考试，听力第二题通常是广播专题、主持人访谈或专家讨论。"
            "Hörtext 2 播放一次，共 10 道 Richtig/Falsch 判断题，题号为 9-18，学生判断陈述是否与听力内容一致。"
            "材料应体现较高信息密度，包含事实、观点、评价、条件、例子、限制和不同说话人的立场。"
            "访谈必须有三个说话人：A 是主持人，B 和 C 是专家、研究者、顾问、大学工作人员或相关领域嘉宾。"
            "用词、句式、说话方式和语气必须同时符合说话人身份、广播访谈场景、具体主题以及老师指定的难度。"
            "standard 难度应符合 B2-C1；easy 应减少嵌套句和抽象名词；hard 可以增加学术表达、让步结构和观点区分。"
            "不要让所有角色说同一种话：主持人应负责引入、追问和总结，专家应给出解释、评价、例子和限制条件。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外的任何文字。"
            "输出顶层字段必须包含 title、topic、speaker_roles、format_note、transcript、segments、statements。"
            "transcript 必须是自然德语访谈，UTF-8 byte length 目标约 4623，允许范围 4400-4850。"
            "transcript 必须能由 segments 按顺序还原为 A:/B:/C: 标注的完整访谈。"
            "每个 segment 只能包含一个说话人的连续发言，并包含 index、speaker_id、speaker_role、text、pause_after_ms、pause_reason。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "pause_reason 用英文短标签，例如 host_transition、normal_turn_switch、thinking、topic_shift、important_information、summary。"
            "statements 必须恰好 10 个元素，number 必须为 9-18，answer 只能是 Richtig 或 Falsch。"
            "每个 statement 必须包含 number、statement、answer、evidence、tested_information、distractor_type、distractor_explanation。"
            "Falsch 陈述必须通过真实考试常见干扰构造，例如 subject_swap、degree_shift、causal_inversion、negation_shift、missing_condition、time_shift。"
            "Richtig 陈述也不能照抄原文，必须使用自然改写，但含义必须被原文明确支持。"
        )

    def _user_prompt(self, data: ListeningAufgabe2Input) -> str:
        flow_instruction = (
            "判断陈述考查的信息点应基本按听力文本顺序出现。"
            if data.information_flow == "sequential"
            else "判断陈述考查的信息点可以局部打乱，但不能破坏题目可答性。"
        )
        balance_instruction = (
            "请生成 5 个 Richtig 和 5 个 Falsch。"
            if data.statement_balance == "balanced"
            else "请大体保持 Richtig 和 Falsch 平衡，不要出现明显偏向。"
        )
        difficulty_instruction = {
            "easy": "偏简单：句子较清晰，抽象表达适量，干扰项不要过度隐蔽。",
            "hard": "偏困难：允许更多学术表达、让步关系、限定条件和观点归属干扰。",
        }.get(data.difficulty, "标准 B2-C1：表达自然，有一定信息密度，但不能晦涩。")
        reference = data.reference_material or "无额外参考素材。"
        return (
            "请根据以下老师输入生成 TestDaF Hörverstehen Hörtext 2 的完整结构化题目物料。\n\n"
            "老师输入：\n"
            f"- 专题主题：{data.topic}\n"
            f"- 参考素材：{reference}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 信息流控制：{data.information_flow}\n"
            f"- R/F 分布：{data.statement_balance}\n\n"
            f"难度语言规则：{difficulty_instruction}\n"
            "请特别注意：用词、说话方式、礼貌程度、学术性、句子长度和信息密度都要匹配角色身份、广播访谈场景和难度。\n\n"
            f"题目顺序规则：{flow_instruction}\n"
            f"答案分布规则：{balance_instruction}\n\n"
            "篇幅要求：\n"
            "- transcript 的 UTF-8 byte length 目标约 4623。\n"
            "- 允许范围为 4400-4850。\n"
            "- 如果内容不足，请自然增加背景解释、专家观点、例子、限制条件、反驳或主持人的追问。\n"
            "- 不要为了凑长度重复无意义内容。\n\n"
            "访谈结构要求：\n"
            "- A 必须是主持人，负责引入话题、转接问题、追问细节和简短总结。\n"
            "- B 和 C 必须是两个身份不同但主题相关的专家或嘉宾。\n"
            "- B 和 C 应有不同视角，不能只是重复彼此观点。\n"
            "- 内容应像真实广播访谈，不要像课堂讲稿或考试说明。\n\n"
            "停顿要求：\n"
            "- 每个 segment 后必须给出 pause_after_ms。\n"
            "- 普通接话使用 200 或 350。\n"
            "- 重要事实、观点结论或限定条件后使用 500 或 750。\n"
            "- 话题转换、主持人总结或段落结束可使用 750 或 1000。\n"
            "- 不要依赖 SSML、特殊占位符或括号说明来控制停顿。\n\n"
            "请严格输出以下 JSON 结构：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "topic": "主题标签或主题短语",\n'
            '  "speaker_roles": {\n'
            '    "A": "Moderator/in",\n'
            '    "B": "专家或嘉宾身份",\n'
            '    "C": "专家或嘉宾身份"\n'
            "  },\n"
            '  "format_note": "kurzes Radiointerview / Expertengespräch",\n'
            '  "transcript": "A: ...\\nB: ...\\nC: ...",\n'
            '  "segments": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "speaker_id": "A",\n'
            '      "speaker_role": "Moderator/in",\n'
            '      "text": "德语发言文本",\n'
            '      "pause_after_ms": 350,\n'
            '      "pause_reason": "host_transition"\n'
            "    }\n"
            "  ],\n"
            '  "statements": [\n'
            "    {\n"
            '      "number": 9,\n'
            '      "statement": "德语判断陈述",\n'
            '      "answer": "Richtig",\n'
            '      "evidence": "原文依据",\n'
            '      "tested_information": "考查的信息点",\n'
            '      "distractor_type": "none",\n'
            '      "distractor_explanation": "为什么该陈述正确或错误"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _segment_expansion_system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 专题访谈扩写专家。当前 Hörtext 2 访谈偏短，"
            "你只负责生成可插入到现有访谈中的新增 segments。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "不要返回完整题目 JSON，只返回 insert_after_index 和 segments。"
            "新增内容必须符合广播访谈语境，补充背景解释、专家观点、例子、限制条件、反问或主持人追问。"
            "新增内容的用词、说话方式和语气必须符合角色身份、场景和难度。"
            "不要改变已有 10 道 R/F 题的答案，不要引入与原访谈冲突的新事实。"
            "speaker_id 只能是 A、B 或 C；A 是主持人，B/C 是专家或嘉宾。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "输出格式为：{\"insert_after_index\": 5, \"segments\": [...]}"
        )

    def _segment_expansion_user_prompt(
        self,
        *,
        data: ListeningAufgabe2Input,
        payload: dict,
        current_bytes: int,
        missing_bytes: int,
        attempt: int,
    ) -> str:
        return (
            f"这是第 {attempt} 次第二题局部扩写。\n"
            f"当前 transcript UTF-8 byte length：{current_bytes}\n"
            f"目标 byte length：约 {TARGET_TRANSCRIPT_BYTES}\n"
            f"估计还需要补充约 {max(missing_bytes, 180)} bytes。\n\n"
            "原始老师输入：\n"
            f"- 专题主题：{data.topic}\n"
            f"- 参考素材：{data.reference_material or '无额外参考素材。'}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 信息流控制：{data.information_flow}\n\n"
            "当前题目 JSON 摘要：\n"
            f"{json.dumps(self._repair_context(payload), ensure_ascii=False, indent=2)}\n\n"
            "请只输出新增片段 JSON：\n"
            "{\n"
            '  "insert_after_index": 5,\n'
            '  "segments": [\n'
            "    {\n"
            '      "speaker_id": "B",\n'
            '      "speaker_role": "角色名",\n'
            '      "text": "新增德语发言",\n'
            '      "pause_after_ms": 500,\n'
            '      "pause_reason": "important_information"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _segment_compression_system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 专题访谈压缩专家。当前 Hörtext 2 访谈偏长，"
            "你只负责压缩指定 segments，不要重写完整 JSON。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "必须保留 R/F 题 evidence 所需信息、speaker_id 和自然德语表达。"
            "压缩后仍要保持角色身份、广播访谈语气和难度匹配。"
            "优先删除冗余铺垫、重复解释和可省略例子。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "输出格式为：{\"segments\": [{\"index\": 4, \"text\": \"...\", \"pause_after_ms\": 350, \"pause_reason\": \"...\"}]}"
        )

    def _segment_compression_user_prompt(
        self,
        *,
        data: ListeningAufgabe2Input,
        payload: dict,
        candidates: list[dict],
        current_bytes: int,
        excess_bytes: int,
        attempt: int,
    ) -> str:
        return (
            f"这是第 {attempt} 次第二题局部压缩。\n"
            f"当前 transcript UTF-8 byte length：{current_bytes}\n"
            f"目标 byte length：约 {TARGET_TRANSCRIPT_BYTES}\n"
            f"估计需要减少约 {max(excess_bytes, 180)} bytes。\n\n"
            "原始老师输入：\n"
            f"- 专题主题：{data.topic}\n"
            f"- 参考素材：{data.reference_material or '无额外参考素材。'}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 信息流控制：{data.information_flow}\n\n"
            "题目 evidence 摘要，压缩时必须保留这些判断依据：\n"
            f"{json.dumps([s.get('evidence', '') for s in payload['statements']], ensure_ascii=False, indent=2)}\n\n"
            "请只压缩以下候选 segments，并返回压缩后的 replacements：\n"
            f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n\n"
            "输出格式：\n"
            "{\n"
            '  "segments": [\n'
            "    {\n"
            '      "index": 4,\n'
            '      "text": "压缩后的德语发言",\n'
            '      "pause_after_ms": 350,\n'
            '      "pause_reason": "normal_turn_switch"\n'
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
            "speaker_roles",
            "format_note",
            "transcript",
            "segments",
            "statements",
        }
        missing = required_keys - payload.keys()
        if missing:
            raise RuntimeError(f"听力第二题生成结果缺少字段：{', '.join(sorted(missing))}")

        speaker_roles = payload["speaker_roles"]
        if not isinstance(speaker_roles, dict) or ALLOWED_SPEAKERS - speaker_roles.keys():
            raise RuntimeError("speaker_roles 必须是包含 A、B、C 的对象")

        segments = payload["segments"]
        if not isinstance(segments, list) or len(segments) < 14:
            raise RuntimeError("听力第二题 segments 至少需要 14 段，以支持专题访谈音频合成")

        seen_speakers = set()
        for index, segment in enumerate(segments, start=1):
            if segment.get("index") != index:
                segment["index"] = index
            for key in ("speaker_id", "speaker_role", "text", "pause_after_ms", "pause_reason"):
                if key not in segment:
                    raise RuntimeError(f"第 {index} 段缺少字段：{key}")
            if segment["speaker_id"] not in ALLOWED_SPEAKERS:
                raise RuntimeError(f"第 {index} 段 speaker_id 必须是 A、B 或 C")
            if int(segment["pause_after_ms"]) not in ALLOWED_PAUSES:
                raise RuntimeError(f"第 {index} 段 pause_after_ms 不在允许档位中")
            seen_speakers.add(segment["speaker_id"])

        if seen_speakers != ALLOWED_SPEAKERS:
            raise RuntimeError("segments 必须同时包含 A、B、C 三个说话人")

        statements = payload["statements"]
        if not isinstance(statements, list) or len(statements) != 10:
            raise RuntimeError("听力第二题必须生成 10 道 Richtig/Falsch 判断题")

        for index, statement in enumerate(statements, start=9):
            if statement.get("number") != index:
                statement["number"] = index
            for key in (
                "statement",
                "answer",
                "evidence",
                "tested_information",
                "distractor_type",
                "distractor_explanation",
            ):
                if key not in statement:
                    raise RuntimeError(f"第 {index} 题缺少字段：{key}")
            if statement["answer"] not in VALID_ANSWERS:
                raise RuntimeError(f"第 {index} 题 answer 必须是 Richtig 或 Falsch")

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
            segment["pause_reason"] = segment.get("pause_reason") or "normal_turn_switch"

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
            "speaker_roles": payload.get("speaker_roles"),
            "format_note": payload.get("format_note"),
            "transcript_bytes": self._transcript_bytes(normalized),
            "segments": payload.get("segments", []),
            "statements": payload.get("statements", []),
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
                raise RuntimeError("扩写片段 speaker_id 必须是 A、B 或 C")
            normalized_new_segments.append(
                {
                    "speaker_id": speaker_id,
                    "speaker_role": segment.get("speaker_role") or speaker_roles[speaker_id],
                    "text": str(segment.get("text", "")).strip(),
                    "pause_after_ms": int(segment.get("pause_after_ms", 350)),
                    "pause_reason": segment.get("pause_reason") or "normal_turn_switch",
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
        evidence_texts = [str(statement.get("evidence", "")) for statement in payload["statements"]]
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
