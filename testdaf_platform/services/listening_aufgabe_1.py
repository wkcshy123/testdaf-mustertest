"""TestDaF 听力 Aufgabe 1 生成服务。"""

import json
from dataclasses import dataclass

import dashscope

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL
from testdaf_platform.services.text_generation import TextGenerationClient
from testdaf_platform.services.generation_utils import parse_json, reorder_by_evidence, gendered_speakers_text

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

MIN_TRANSCRIPT_BYTES = 2000
MAX_TRANSCRIPT_BYTES = 2600
TARGET_TRANSCRIPT_BYTES = 2300
HARD_MIN_TRANSCRIPT_BYTES = 1800
HARD_MAX_TRANSCRIPT_BYTES = 2800
MAX_LENGTH_REPAIR_ATTEMPTS = 3


class TranscriptLengthError(RuntimeError):
    """听力原文长度不满足考试材料篇幅要求。"""

    def __init__(self, current_bytes: int):
        self.current_bytes = current_bytes
        super().__init__(
            f"听力原文 UTF-8 长度应在 {MIN_TRANSCRIPT_BYTES}-{MAX_TRANSCRIPT_BYTES} 字节之间，"
            f"当前为 {current_bytes} 字节"
        )


@dataclass(frozen=True)
class ListeningAufgabe1Input:
    scenario: str
    reference_material: str
    difficulty: str
    information_flow: str
    speaker_genders: dict[str, str]


class ListeningAufgabe1Generator:
    """生成 TestDaF 听力第一题的结构化物料。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model
        self.client = TextGenerationClient(model=model)

    def generate(self, api_key: str, data: ListeningAufgabe1Input, *, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(10, "调用文本模型生成初稿...")
        payload = self._normalize_payload(self._generate_initial_payload(api_key, data))

        if progress_callback:
            progress_callback(70, "初稿完成，结构验证中...")

        last_bytes: int | None = None
        stuck_count = 0

        for attempt in range(MAX_LENGTH_REPAIR_ATTEMPTS + 1):
            self._validate_structure(payload)
            payload = self._normalize_payload(payload)
            current_bytes = self._transcript_bytes(payload)

            if MIN_TRANSCRIPT_BYTES <= current_bytes <= MAX_TRANSCRIPT_BYTES:
                if progress_callback:
                    progress_callback(95, "答案排序与元数据写入中...")
                return self._with_length_metadata(
                    reorder_by_evidence(payload, "questions", "transcript", start_number=1), "ideal"
                )

            if HARD_MIN_TRANSCRIPT_BYTES <= current_bytes <= HARD_MAX_TRANSCRIPT_BYTES:
                if progress_callback:
                    progress_callback(95, "答案排序与元数据写入中...")
                return self._with_length_metadata(
                    reorder_by_evidence(payload, "questions", "transcript", start_number=1),
                    "accepted",
                )

            if attempt >= MAX_LENGTH_REPAIR_ATTEMPTS:
                raise TranscriptLengthError(current_bytes)

            if current_bytes == last_bytes:
                stuck_count += 1
                if stuck_count >= 2:
                    raise RuntimeError(
                        f"生成陷入死循环：transcript 长度连续 {stuck_count + 1} 次停留在 {current_bytes} bytes，"
                        f"已自动终止。请尝试更换主题或降低难度后重新生成。"
                    )
            else:
                stuck_count = 0
                last_bytes = current_bytes

            repair_pct = 75 + attempt * 6
            if current_bytes < MIN_TRANSCRIPT_BYTES:
                if progress_callback:
                    progress_callback(repair_pct, f"长度偏短，扩写第 {attempt + 1}/{MAX_LENGTH_REPAIR_ATTEMPTS} 次...")
                payload = self._expand_segments(
                    api_key=api_key,
                    data=data,
                    payload=payload,
                    current_bytes=current_bytes,
                    attempt=attempt + 1,
                )
            else:
                if progress_callback:
                    progress_callback(repair_pct, f"长度偏长，压缩第 {attempt + 1}/{MAX_LENGTH_REPAIR_ATTEMPTS} 次...")
                payload = self._compress_segments(
                    api_key=api_key,
                    data=data,
                    payload=payload,
                    current_bytes=current_bytes,
                    attempt=attempt + 1,
                )

        raise RuntimeError("听力题生成失败：超过最大篇幅修复次数")

    def _generate_initial_payload(self, api_key: str, data: ListeningAufgabe1Input) -> dict:
        content = self.client.generate_text(
            api_key=api_key,
            messages=[
                {
                    "role": "system",
                    "content": self._system_prompt(data),
                },
                {
                    "role": "user",
                    "content": self._user_prompt(data),
                },
            ],
            max_tokens=6000,
        )

        return parse_json(content, label="听力 Aufg.1 JSON")

    def _expand_segments(
        self,
        *,
        api_key: str,
        data: ListeningAufgabe1Input,
        payload: dict,
        current_bytes: int,
        attempt: int,
    ) -> dict:
        missing_bytes = TARGET_TRANSCRIPT_BYTES - current_bytes
        content = self.client.generate_text(
            api_key=api_key,
            messages=[
                {
                    "role": "system",
                    "content": self._segment_expansion_system_prompt(),
                },
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
            max_tokens=2500,
        )

        repair = parse_json(content)
        new_segments = self._extract_repair_segments(repair)
        insert_after = int(repair.get("insert_after_index", max(len(payload["segments"]) - 1, 1)))
        return self._insert_segments(payload, new_segments, insert_after)

    def _compress_segments(
        self,
        *,
        api_key: str,
        data: ListeningAufgabe1Input,
        payload: dict,
        current_bytes: int,
        attempt: int,
    ) -> dict:
        excess_bytes = current_bytes - TARGET_TRANSCRIPT_BYTES
        candidates = self._compression_candidates(payload)
        content = self.client.generate_text(
            api_key=api_key,
            messages=[
                {
                    "role": "system",
                    "content": self._segment_compression_system_prompt(),
                },
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
            max_tokens=2500,
        )

        repair = parse_json(content)
        replacements = self._extract_repair_segments(repair)
        return self._replace_segments(payload, replacements)


    def _system_prompt(self, data: ListeningAufgabe1Input) -> str:
        gender_text = gendered_speakers_text(data.speaker_genders)
        return (
            f"{gender_text}"
            "这是强制硬约束——如果指定某说话人为男性，则该角色只能是男性名字和男性身份；"
            "如果指定为女性，则只能是女性名字和女性身份。性别错配的生成视为不合格。\n"
            "你是 TestDaF Hörverstehen 出题专家，负责生成 TestDaF 听力第一题 Hörtext 1 的完整结构化物料。"
            "TestDaF 是面向准备进入德国高校学习者的德语考试，听力部分要求考生在真实大学语境中提取关键信息。"
            "Hörtext 1 的典型场景是校园、大学行政、课程咨询、图书馆、住宿、实习、社团、考试报名或学生服务。"
            "Hörtext 1 通常是两人自然对话，播放一次，共 8 道简短回答题，学生用 Stichwörter 作答。"
            "对话文本中禁止出现括号标注的情绪提示或舞台提示，如 (lacht)、(seufzt)、"
            "(stöhnt)、(überlegt) 等——这是一段纯语音对话，不是剧本。"
            "如需表达情感，请写入口语感叹词（如 Ach!、Oh!、Na ja...、Hm.），"
            "并由 pause_reason 标注情绪转折（如 thinking、hesitation、sigh、amusement）。"
            "题目应考察具体事实、原因、计划、条件、需求、经历、任务、建议或后续安排。"
            "语言应自然、清晰、符合德国大学生活语境，难度面向 B2-C1，不能过度戏剧化。"
            "出题内容质量要求：\n"
            "- 对话信息必须单一无歧义：每个答案点对应原文中的唯一明确出处，避免模糊或可多解的表达。\n"
            "- 如果一个问题存在多个可能正确的信息切入点（如问'有哪些条件'时有多个条件），请在 acceptable_variants 中列出所有正确回答方式，不要只接受一种。\n"
            "- 不要把随机地名、机构全称中的冗长复合词作为唯一可接受的答案核心。例如机构名称 Jugendfreizeiteinrichtung Kleine Welt 应将 Kleine Welt 或 Jugendfreizeiteinrichtung Kleine Welt 作为 answer，而非强迫学生写完包含地名的全称。\n"
            "- 日期类答案必须同时接受带点和无点的格式（如 15. März 和 15 März）。\n"
            "- 德语时态变化（Präsens/Präteritum/Perfekt）不构成判分差异：例如 sprachen 和 sprechen 视为等值。\n"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外的任何文字。"
            "输出顶层字段必须包含 title、topic、speaker_roles、relationship、transcript、segments、questions。"
            "transcript 必须是自然德语对话，UTF-8 byte length 目标约 2000，允许范围 2000-2600。"
            "对话只能有两个说话人，speaker_id 只能是 A 或 B。speaker_roles 必须是对象，包含 A 和 B。"
            "必须生成 segments 数组；每个 segment 只能包含一个说话人的连续发言。"
            "transcript 必须能由 segments 按顺序还原为 A:/B: 标注的完整对话。"
            "每个 segment 必须包含 index、speaker_id、speaker_role、text、pause_after_ms、pause_reason。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "200 毫秒仅用于被打断或急切抢答；正常接话使用 350 或 500；"
            "重要信息、规则说明、思考或确认后使用 500 或 750；"
            "话题转换或收尾使用 750 或 1000，确保对话衔接自然不抢话。"
            "pause_reason 用英文短标签，例如 normal_turn_switch、thinking、topic_shift、important_information、closing。"
            "questions 必须恰好 8 个元素，每个元素包含 number、prompt、required_points、answer、acceptable_variants、evidence。"
            "每道题的 evidence 必须能在 transcript 中找到对应的原文片段；题目必须按 evidence 在 transcript 中的出现顺序排列，从前往后不颠倒。"
            "prompt 必须是德语问题，符合 TestDaF 风格；answer 必须是关键词或短语，不要写成长句。"
            "可以自然包含少量 required_points=2 的题目，但不要超过 3 题。\n"
            "acceptable_variants 要求（模拟 TestDaF 官方 Lösungsschlüssel 答案密钥）：\n"
            "- 每条题目必须列出 2-4 个常见可接受变体，覆盖不同学生可能给出的等义表达。\n"
            "- 必须包含：答案关键词的核心同义词、带/不带冠词的变体、常见介词搭配变体。\n"
            "- 如果答案是一个名词（如 Umweltschutz），变体应包含：der Umweltschutz、Naturschutz、den Umweltschutz 等。\n"
            "- 如果答案是一个动词短语（如 an der Uni studieren），变体应包含：studiert an der Uni、in der Uni studieren、besucht die Uni 等。\n"
            "- 如果答案是一个数字或日期，变体应包含不同书写格式（如 15. Mai、15.05.、Mai 2025）。\n"
            "- 不要添加明显错误或无关的变体。每个变体必须是评分员可能判对的有效答案。"
        )

    def _user_prompt(self, data: ListeningAufgabe1Input) -> str:
        flow_instruction = (
            "题目答案点应基本按听力文本顺序出现。"
            if data.information_flow == "sequential"
            else "允许答案点在文本中局部打乱，但仍必须保持听力文本自然、可听、可答。"
        )
        reference = data.reference_material or "无额外参考素材。"
        return (
            "请根据以下老师输入生成 TestDaF Hörverstehen Hörtext 1 的完整结构化题目物料。\n\n"
            "老师输入：\n"
            f"- 场景：{data.scenario}\n"
            f"- 参考素材：{reference}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 信息流控制：{data.information_flow}\n"
            f"- 说话人性别：{gendered_speakers_text(data.speaker_genders)}\n\n"
            f"信息流规则：{flow_instruction}\n\n"
            "篇幅要求：\n"
            "- transcript 的 UTF-8 byte length 目标约 2000。\n"
            "- 允许范围为 2000-2600。\n"
            "- 如果内容不足，请自然增加对话细节、背景信息、流程说明、条件限制或后续安排。\n"
            "- 不要为了凑长度重复无意义内容。\n\n"
            "对话结构要求：\n"
            "- 两个说话人必须轮流自然对话。\n"
            "- 请自动决定说话人身份与关系。\n"
            "- 场景应符合德国大学或校园语境。\n"
            "- 不要出现考试之外的解释性文字。\n\n"
            "停顿要求：\n"
            "- 每个 segment 后必须给出 pause_after_ms。\n"
            "- 200 毫秒仅用于被打断或急切抢答；正常接话使用 350 或 500。\n"
            "- 信息确认、规则说明、重要信息后使用 500 或 750。\n"
            "- 话题转换或收尾可使用 750 或 1000，确保对话衔接自然不抢话。\n"
            "- 不要依赖 SSML、特殊占位符或括号说明来控制停顿。\n\n"
            "请严格输出以下 JSON 结构：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "topic": "主题标签或主题短语",\n'
            '  "speaker_roles": {\n'
            '    "A": "说话人A身份",\n'
            '    "B": "说话人B身份"\n'
            "  },\n"
            '  "relationship": "两人关系",\n'
            '  "transcript": "A: ...\\nB: ...",\n'
            '  "segments": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "speaker_id": "A",\n'
            '      "speaker_role": "说话人A身份",\n'
            '      "text": "德语发言文本",\n'
            '      "pause_after_ms": 350,\n'
            '      "pause_reason": "normal_turn_switch"\n'
            "    }\n"
            "  ],\n"
            '  "questions": [\n'
            "    {\n"
            '      "number": 1,\n'
            '      "prompt": "德语问题",\n'
            '      "required_points": 1,\n'
            '      "answer": ["标准答案"],\n'
            '      "acceptable_variants": ["可接受变体1", "变体2（同义词）", "变体3（不同介词）"],\n'
            '      "evidence": "原文依据"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _segment_expansion_system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 对话扩写专家。当前 Hörtext 1 对话偏短，"
            "你只负责生成可插入到现有对话中的新增 segments。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "不要返回完整题目 JSON，只返回 insert_after_index 和 segments。"
            "新增内容必须保持德国大学校园语境，补充流程说明、条件限制、确认信息、后续安排或礼貌性转折。"
            "不要改变已有 8 道题的答案，不要引入与原对话冲突的新事实。"
            "每个新增 segment 只能包含一个说话人的连续发言，speaker_id 只能是 A 或 B。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "输出格式为：{\"insert_after_index\": 3, \"segments\": [...]}"
        )

    def _segment_expansion_user_prompt(
        self,
        *,
        data: ListeningAufgabe1Input,
        payload: dict,
        current_bytes: int,
        missing_bytes: int,
        attempt: int,
    ) -> str:
        return (
            f"这是第 {attempt} 次局部扩写。\n"
            f"当前 transcript UTF-8 byte length：{current_bytes}\n"
            f"目标 byte length：约 {TARGET_TRANSCRIPT_BYTES}\n"
            f"估计还需要补充约 {max(missing_bytes, 120)} bytes。\n\n"
            "原始老师输入：\n"
            f"- 场景：{data.scenario}\n"
            f"- 参考素材：{data.reference_material or '无额外参考素材。'}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 信息流控制：{data.information_flow}\n\n"
            "当前题目 JSON 摘要：\n"
            f"{json.dumps(self._repair_context(payload), ensure_ascii=False, indent=2)}\n\n"
            "请只输出新增片段 JSON：\n"
            "{\n"
            '  "insert_after_index": 3,\n'
            '  "segments": [\n'
            "    {\n"
            '      "speaker_id": "A",\n'
            '      "speaker_role": "角色名",\n'
            '      "text": "新增德语发言",\n'
            '      "pause_after_ms": 350,\n'
            '      "pause_reason": "normal_turn_switch"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _segment_compression_system_prompt(self) -> str:
        return (
            "你是 TestDaF Hörverstehen 对话压缩专家。当前 Hörtext 1 对话偏长，"
            "你只负责压缩指定 segments，不要重写完整 JSON。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "必须保留题目答案所需信息、speaker_id 和自然德语表达。"
            "优先删除寒暄、重复确认和冗余解释。"
            "pause_after_ms 只能从 200、350、500、750、1000 中选择。"
            "输出格式为：{\"segments\": [{\"index\": 3, \"text\": \"...\", \"pause_after_ms\": 350, \"pause_reason\": \"...\"}]}"
        )

    def _segment_compression_user_prompt(
        self,
        *,
        data: ListeningAufgabe1Input,
        payload: dict,
        candidates: list[dict],
        current_bytes: int,
        excess_bytes: int,
        attempt: int,
    ) -> str:
        return (
            f"这是第 {attempt} 次局部压缩。\n"
            f"当前 transcript UTF-8 byte length：{current_bytes}\n"
            f"目标 byte length：约 {TARGET_TRANSCRIPT_BYTES}\n"
            f"估计需要减少约 {max(excess_bytes, 120)} bytes。\n\n"
            "原始老师输入：\n"
            f"- 场景：{data.scenario}\n"
            f"- 参考素材：{data.reference_material or '无额外参考素材。'}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 信息流控制：{data.information_flow}\n\n"
            "题目 evidence 摘要，压缩时必须保留这些答案依据：\n"
            f"{json.dumps([q.get('evidence', '') for q in payload['questions']], ensure_ascii=False, indent=2)}\n\n"
            "请只压缩以下候选 segments，并返回压缩后的 replacements：\n"
            f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n\n"
            "输出格式：\n"
            "{\n"
            '  "segments": [\n'
            "    {\n"
            '      "index": 3,\n'
            '      "text": "压缩后的德语发言",\n'
            '      "pause_after_ms": 350,\n'
            '      "pause_reason": "normal_turn_switch"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

    def _validate_payload(self, payload: dict) -> None:
        self._validate_structure(payload)
        payload = self._normalize_payload(payload)
        transcript_len = self._transcript_bytes(payload)
        if not MIN_TRANSCRIPT_BYTES <= transcript_len <= MAX_TRANSCRIPT_BYTES:
            raise TranscriptLengthError(transcript_len)

    def _validate_structure(self, payload: dict) -> None:
        required_keys = {
            "title",
            "topic",
            "speaker_roles",
            "relationship",
            "transcript",
            "segments",
            "questions",
        }
        missing = required_keys - payload.keys()
        if missing:
            raise RuntimeError(f"听力题生成结果缺少字段：{', '.join(sorted(missing))}")

        speaker_roles = payload["speaker_roles"]
        if not isinstance(speaker_roles, dict) or {"A", "B"} - speaker_roles.keys():
            raise RuntimeError("speaker_roles 必须是包含 A 和 B 的对象")

        segments = payload["segments"]
        if not isinstance(segments, list) or len(segments) < 8:
            raise RuntimeError("segments 至少需要 8 段，以支持两人对话音频合成")

        seen_speakers = set()
        allowed_pauses = {200, 350, 500, 750, 1000}
        for index, segment in enumerate(segments, start=1):
            if segment.get("index") != index:
                segment["index"] = index
            for key in ("speaker_id", "speaker_role", "text", "pause_after_ms", "pause_reason"):
                if key not in segment:
                    raise RuntimeError(f"第 {index} 段缺少字段：{key}")
            if segment["speaker_id"] not in {"A", "B"}:
                raise RuntimeError(f"第 {index} 段 speaker_id 必须是 A 或 B")
            if int(segment["pause_after_ms"]) not in allowed_pauses:
                raise RuntimeError(f"第 {index} 段 pause_after_ms 不在允许档位中")
            seen_speakers.add(segment["speaker_id"])

        if seen_speakers != {"A", "B"}:
            raise RuntimeError("segments 必须同时包含 A 和 B 两个说话人")

        questions = payload["questions"]
        if not isinstance(questions, list) or len(questions) != 8:
            raise RuntimeError("听力第一题必须生成 8 道题")

        for index, question in enumerate(questions, start=1):
            if question.get("number") != index:
                question["number"] = index
            for key in ("prompt", "required_points", "answer", "acceptable_variants", "evidence"):
                if key not in question:
                    raise RuntimeError(f"第 {index} 题缺少字段：{key}")

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
        return {
            "title": payload.get("title"),
            "topic": payload.get("topic"),
            "speaker_roles": payload.get("speaker_roles"),
            "relationship": payload.get("relationship"),
            "transcript_bytes": self._transcript_bytes(self._normalize_payload(payload.copy())),
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
            if speaker_id not in {"A", "B"}:
                raise RuntimeError("扩写片段 speaker_id 必须是 A 或 B")
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
        return sorted(pool, key=lambda item: item["utf8_bytes"], reverse=True)[:4]
