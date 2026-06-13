"""TestDaF 阅读题生成服务。"""

import json
import re
from dataclasses import dataclass

import dashscope
from dashscope import Generation

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

AUFGABE_1_OFFER_TARGET_BYTES = 505
AUFGABE_1_OFFER_MIN_BYTES = 460
AUFGABE_1_OFFER_MAX_BYTES = 560
AUFGABE_1_OFFER_HARD_MIN_BYTES = 420
AUFGABE_1_OFFER_HARD_MAX_BYTES = 620

AUFGABE_2_TARGET_BYTES = 4103
AUFGABE_2_MIN_BYTES = 3900
AUFGABE_2_MAX_BYTES = 4300
AUFGABE_2_HARD_MIN_BYTES = 3700
AUFGABE_2_HARD_MAX_BYTES = 4500

AUFGABE_3_TARGET_BYTES = 4963
AUFGABE_3_MIN_BYTES = 4700
AUFGABE_3_MAX_BYTES = 5200
AUFGABE_3_HARD_MIN_BYTES = 4500
AUFGABE_3_HARD_MAX_BYTES = 5400

MAX_READING_LENGTH_REPAIR_ATTEMPTS = 3


@dataclass(frozen=True)
class ReadingAufgabe1Input:
    topic: str
    reference_material: str
    difficulty: str
    offer_count: int
    no_match_count: int


@dataclass(frozen=True)
class ReadingAufgabe2Input:
    topic: str
    reference_material: str
    difficulty: str
    text_length: str
    skill_focus: str


@dataclass(frozen=True)
class ReadingAufgabe3Input:
    topic: str
    reference_material: str
    difficulty: str
    judgement_balance: str
    unsupported_items: str


class BaseReadingGenerator:
    """阅读生成器基础工具。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model

    def _call_generation(self, api_key: str, system_prompt: str, user_prompt: str, max_tokens: int) -> dict:
        resp = Generation.call(
            model=self.model,
            api_key=api_key,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")
        content = resp.output.text
        if not content:
            raise RuntimeError("API 未返回阅读题内容")
        return self._parse_json(content)

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

    def _call_repair(self, api_key: str, system_prompt: str, user_prompt: str, max_tokens: int) -> dict:
        return self._call_generation(api_key, system_prompt, user_prompt, max_tokens)

    def _normalize_long_text_payload(self, payload: dict, *, min_paragraphs: int = 5) -> dict:
        text = str(payload.get("reading_text", "")).strip()
        if not text:
            return payload

        paragraphs = payload.get("paragraphs")
        if not self._has_enough_paragraphs(paragraphs, min_paragraphs):
            paragraph_texts = self._split_reading_text(text, min_paragraphs)
            payload["paragraphs"] = [
                {"index": index, "text": paragraph}
                for index, paragraph in enumerate(paragraph_texts, start=1)
            ]
        else:
            normalized = []
            for index, paragraph in enumerate(paragraphs, start=1):
                paragraph_text = paragraph.get("text") if isinstance(paragraph, dict) else str(paragraph)
                normalized.append({"index": index, "text": str(paragraph_text).strip()})
            payload["paragraphs"] = [item for item in normalized if item["text"]]

        payload["reading_text"] = "\n\n".join(item["text"] for item in payload["paragraphs"])
        return payload

    def _repair_long_text_length(
        self,
        *,
        api_key: str,
        payload: dict,
        task_label: str,
        target_bytes: int,
        ideal_min_bytes: int,
        ideal_max_bytes: int,
        hard_min_bytes: int,
        hard_max_bytes: int,
        min_paragraphs: int = 5,
    ) -> dict:
        payload = self._normalize_long_text_payload(payload, min_paragraphs=min_paragraphs)
        for attempt in range(MAX_READING_LENGTH_REPAIR_ATTEMPTS + 1):
            current = _utf8_bytes(payload.get("reading_text", ""))
            if hard_min_bytes <= current <= hard_max_bytes:
                return payload
            if attempt >= MAX_READING_LENGTH_REPAIR_ATTEMPTS:
                raise RuntimeError(
                    f"{task_label} reading_text UTF-8 长度目标约 {target_bytes} bytes，"
                    f"硬范围为 {hard_min_bytes}-{hard_max_bytes} bytes，当前为 {current} bytes"
                )

            payload = self._repair_long_text_once(
                api_key=api_key,
                payload=payload,
                task_label=task_label,
                current_bytes=current,
                target_bytes=target_bytes,
                ideal_min_bytes=ideal_min_bytes,
                ideal_max_bytes=ideal_max_bytes,
                hard_min_bytes=hard_min_bytes,
                hard_max_bytes=hard_max_bytes,
                min_paragraphs=min_paragraphs,
            )
        return payload

    def _repair_long_text_once(
        self,
        *,
        api_key: str,
        payload: dict,
        task_label: str,
        current_bytes: int,
        target_bytes: int,
        ideal_min_bytes: int,
        ideal_max_bytes: int,
        hard_min_bytes: int,
        hard_max_bytes: int,
        min_paragraphs: int,
    ) -> dict:
        action = "扩写" if current_bytes < hard_min_bytes else "压缩"
        repair = self._call_repair(
            api_key=api_key,
            system_prompt=(
                "你是 TestDaF Leseverstehen 文本长度修复专家。"
                "你只修复阅读正文，不重写题目、答案或判断项。"
                "必须只输出合法 JSON，不要输出 Markdown、解释或代码块。"
                "返回字段必须包含 paragraphs；每个 paragraph 包含 index 和 text。"
            ),
            user_prompt=(
                f"请对 {task_label} 的阅读正文进行{action}，使 reading_text 的 UTF-8 byte length "
                f"接近 {target_bytes}，理想范围 {ideal_min_bytes}-{ideal_max_bytes}，"
                f"硬范围 {hard_min_bytes}-{hard_max_bytes}。当前为 {current_bytes} bytes。\n\n"
                "修复要求：\n"
                f"- 保持 {min_paragraphs}-8 个自然段，段落逻辑清楚。\n"
                "- 保持原主题、论证方向、难度和 TestDaF 阅读风格。\n"
                "- 不要新增会使现有题目答案明显失效的关键信息；如需扩写，优先增加背景、例子、原因、限制条件或过渡论证。\n"
                "- 如需压缩，删除冗余修饰和重复解释，不改变核心事实。\n"
                "- 只返回 JSON：{\"paragraphs\": [{\"index\": 1, \"text\": \"...\"}]}\n\n"
                "当前正文物料：\n"
                f"{json.dumps(self._long_text_repair_context(payload), ensure_ascii=False, indent=2)}"
            ),
            max_tokens=6500,
        )
        paragraphs = repair.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs:
            raise RuntimeError(f"{task_label} 长度修复未返回 paragraphs")
        payload["paragraphs"] = paragraphs
        return self._normalize_long_text_payload(payload, min_paragraphs=min_paragraphs)

    def _long_text_repair_context(self, payload: dict) -> dict:
        return {
            "title": payload.get("title"),
            "topic": payload.get("topic"),
            "current_bytes": _utf8_bytes(payload.get("reading_text", "")),
            "paragraphs": payload.get("paragraphs", []),
        }

    def _has_enough_paragraphs(self, paragraphs: object, min_paragraphs: int) -> bool:
        if not isinstance(paragraphs, list):
            return False
        valid = 0
        for paragraph in paragraphs:
            if isinstance(paragraph, dict):
                text = str(paragraph.get("text", "")).strip()
            else:
                text = str(paragraph).strip()
            if text:
                valid += 1
        return valid >= min_paragraphs

    def _split_reading_text(self, text: str, min_paragraphs: int) -> list[str]:
        by_blank_lines = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        if len(by_blank_lines) >= min_paragraphs:
            return by_blank_lines

        sentences = re.split(r"(?<=[.!?])\s+", _normalize_whitespace(text))
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        if len(sentences) < min_paragraphs:
            return self._split_by_length(_normalize_whitespace(text), min_paragraphs)

        target_count = max(min_paragraphs, min(8, len(sentences) // 3 or min_paragraphs))
        target_chars = max(120, len(text) // target_count)
        paragraphs = []
        current = []
        current_len = 0
        for sentence in sentences:
            current.append(sentence)
            current_len += len(sentence)
            if current_len >= target_chars and len(paragraphs) < target_count - 1:
                paragraphs.append(" ".join(current).strip())
                current = []
                current_len = 0
        if current:
            paragraphs.append(" ".join(current).strip())
        if len(paragraphs) < min_paragraphs:
            return self._split_by_length(_normalize_whitespace(text), min_paragraphs)
        return paragraphs

    def _split_by_length(self, text: str, min_paragraphs: int) -> list[str]:
        if not text:
            return []
        chunk_size = max(1, len(text) // min_paragraphs)
        chunks = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                boundary = text.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            chunks.append(text[start:end].strip())
            start = end
        return [chunk for chunk in chunks if chunk]


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _utf8_bytes(value: str) -> int:
    return len(value.encode("utf-8"))


class ReadingAufgabe1Generator(BaseReadingGenerator):
    """生成 TestDaF 阅读第一题：信息匹配。"""

    def generate(self, api_key: str, data: ReadingAufgabe1Input) -> dict:
        payload = self._call_generation(api_key, self._system_prompt(), self._user_prompt(data), 7000)
        self._validate(payload, data.offer_count, data.no_match_count, validate_lengths=False)
        payload = self._repair_offer_lengths(api_key, payload, data.offer_count, data.no_match_count)
        self._validate(payload, data.offer_count, data.no_match_count)
        self._annotate_offer_lengths(payload)
        return payload

    def _system_prompt(self) -> str:
        return (
            "你是 TestDaF Leseverstehen 出题专家，负责生成阅读第一题 Lesetext 1 的完整结构化物料。"
            "Lesetext 1 是信息匹配题：考生阅读若干短广告、课程介绍、服务说明或项目简介，"
            "再把 10 个具体人物需求匹配到合适文本；若没有合适文本，答案为 I。"
            "该题考查快速扫描、关键词定位、同义改写、条件匹配和排除干扰信息。"
            "难度低于 Lesetext 2/3，但不能只做明显词面匹配，必须有适量同义改写。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "顶层字段必须包含 title、topic、scenario、offers、profiles、answers。"
            "offers 必须使用 A-H 标签；profiles 必须是 1-10；answers 必须逐题给出 answer、evidence、matching_reason。"
            "每个 offer 最多只能被使用一次；部分 profiles 必须答案为 I，表示没有合适文本。"
            "每个 offer.text 的 UTF-8 byte length 目标约 505，理想范围 460-560。"
        )

    def _user_prompt(self, data: ReadingAufgabe1Input) -> str:
        reference = data.reference_material or "无额外参考素材。"
        return (
            "请生成 TestDaF Leseverstehen Lesetext 1 信息匹配题。\n\n"
            f"- 主题领域：{data.topic}\n"
            f"- 参考素材：{reference}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 短文本数量：{data.offer_count}，标签必须为 A-H\n"
            "- 人物需求数量：10，编号 1-10\n"
            f"- 无匹配项数量：约 {data.no_match_count} 个，答案为 I\n\n"
            "篇幅要求：每个 A-H 短文本 text 的 UTF-8 byte length 目标约 505；"
            "理想范围 460-560；不要写成很短的广告标题，也不要写成长篇文章。\n\n"
            "语言要求：短文本应像真实大学服务、课程、活动、奖学金、实习或培训介绍；"
            "人物需求应具体，包含专业背景、目标、限制条件或证书需求。\n\n"
            "请输出 JSON：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "topic": "主题",\n'
            '  "scenario": "德语任务说明",\n'
            '  "offers": [{"label": "A", "heading": "标题", "text": "短文本"}],\n'
            '  "profiles": [{"number": 1, "need": "人物需求"}],\n'
            '  "answers": [{"number": 1, "answer": "A", "evidence": "依据", "matching_reason": "匹配理由"}]\n'
            "}\n"
        )

    def _validate(
        self,
        payload: dict,
        offer_count: int,
        no_match_count: int,
        *,
        validate_lengths: bool = True,
    ) -> None:
        for key in ("title", "topic", "scenario", "offers", "profiles", "answers"):
            if key not in payload:
                raise RuntimeError(f"阅读第一题生成结果缺少字段：{key}")
        offers = payload["offers"]
        profiles = payload["profiles"]
        answers = payload["answers"]
        if not isinstance(offers, list) or len(offers) != offer_count:
            raise RuntimeError(f"阅读第一题必须生成 {offer_count} 个短文本")
        expected_labels = [chr(ord("A") + index) for index in range(offer_count)]
        labels = [offer.get("label") for offer in offers]
        if labels != expected_labels:
            raise RuntimeError("阅读第一题 offers 标签必须依次为 A-H")
        if not isinstance(profiles, list) or len(profiles) != 10:
            raise RuntimeError("阅读第一题必须生成 10 个人物需求")
        if not isinstance(answers, list) or len(answers) != 10:
            raise RuntimeError("阅读第一题必须生成 10 个答案")
        used = []
        valid_answers = set(expected_labels) | {"I"}
        for index, item in enumerate(answers, start=1):
            if item.get("number") != index:
                item["number"] = index
            if item.get("answer") not in valid_answers:
                raise RuntimeError(f"第 {index} 题答案必须是 A-H 或 I")
            if item["answer"] != "I":
                used.append(item["answer"])
            for key in ("evidence", "matching_reason"):
                if key not in item:
                    raise RuntimeError(f"第 {index} 题答案缺少字段：{key}")
        if len(used) != len(set(used)):
            raise RuntimeError("阅读第一题每个短文本最多只能被使用一次")
        if sum(1 for item in answers if item["answer"] == "I") < max(1, no_match_count - 1):
            raise RuntimeError("阅读第一题无匹配项数量不足")

        if validate_lengths:
            self._validate_offer_lengths(offers)

    def _validate_offer_lengths(self, offers: list[dict]) -> None:
        invalid = []
        for offer in offers:
            label = offer.get("label", "?")
            current = _utf8_bytes(str(offer.get("text", "")))
            if current < AUFGABE_1_OFFER_HARD_MIN_BYTES or current > AUFGABE_1_OFFER_HARD_MAX_BYTES:
                invalid.append(f"{label}: {current} bytes")
        if invalid:
            raise RuntimeError(
                "阅读第一题每个短文本 UTF-8 长度目标约 "
                f"{AUFGABE_1_OFFER_TARGET_BYTES} bytes，硬范围为 "
                f"{AUFGABE_1_OFFER_HARD_MIN_BYTES}-{AUFGABE_1_OFFER_HARD_MAX_BYTES} bytes；"
                f"不合格项：{', '.join(invalid)}"
            )

    def _repair_offer_lengths(
        self,
        api_key: str,
        payload: dict,
        offer_count: int,
        no_match_count: int,
    ) -> dict:
        for attempt in range(MAX_READING_LENGTH_REPAIR_ATTEMPTS + 1):
            invalid = self._invalid_offers(payload["offers"])
            if not invalid:
                return payload
            if attempt >= MAX_READING_LENGTH_REPAIR_ATTEMPTS:
                self._validate_offer_lengths(payload["offers"])

            payload = self._repair_offers_once(api_key, payload, invalid)
            self._validate(payload, offer_count, no_match_count, validate_lengths=False)
        return payload

    def _invalid_offers(self, offers: list[dict]) -> list[dict]:
        invalid = []
        for offer in offers:
            current = _utf8_bytes(str(offer.get("text", "")))
            if current < AUFGABE_1_OFFER_HARD_MIN_BYTES or current > AUFGABE_1_OFFER_HARD_MAX_BYTES:
                invalid.append(
                    {
                        "label": offer.get("label"),
                        "heading": offer.get("heading"),
                        "text": offer.get("text"),
                        "current_bytes": current,
                        "action": "扩写" if current < AUFGABE_1_OFFER_HARD_MIN_BYTES else "压缩",
                    }
                )
        return invalid

    def _repair_offers_once(self, api_key: str, payload: dict, invalid: list[dict]) -> dict:
        repair = self._call_repair(
            api_key=api_key,
            system_prompt=(
                "你是 TestDaF Leseverstehen Lesetext 1 短文本长度修复专家。"
                "你只修复指定 offer.text，不修改标签、题目、人物需求或答案。"
                "必须只输出合法 JSON，不要输出 Markdown、解释或代码块。"
                "返回字段必须是 offers，每项包含 label 和 text。"
            ),
            user_prompt=(
                "请修复以下 Lesetext 1 短文本长度。每个 text 的 UTF-8 byte length "
                f"目标约 {AUFGABE_1_OFFER_TARGET_BYTES}，理想范围 "
                f"{AUFGABE_1_OFFER_MIN_BYTES}-{AUFGABE_1_OFFER_MAX_BYTES}，硬范围 "
                f"{AUFGABE_1_OFFER_HARD_MIN_BYTES}-{AUFGABE_1_OFFER_HARD_MAX_BYTES}。\n\n"
                "修复要求：\n"
                "- 保持真实大学服务、课程、项目、活动或培训介绍的风格。\n"
                "- 保持原 heading、主题方向和可匹配信息，不要制造会破坏现有答案的新匹配关系。\n"
                "- 过短则补充对象、条件、时间、申请要求、限制或服务细节；过长则删减冗余修饰。\n"
                "- 只返回 JSON：{\"offers\": [{\"label\": \"A\", \"text\": \"...\"}]}\n\n"
                "整体题目上下文：\n"
                f"{json.dumps(self._offer_repair_context(payload, invalid), ensure_ascii=False, indent=2)}"
            ),
            max_tokens=4000,
        )
        repaired = repair.get("offers")
        if not isinstance(repaired, list) or not repaired:
            raise RuntimeError("阅读第一题长度修复未返回 offers")
        by_label = {item.get("label"): str(item.get("text", "")).strip() for item in repaired}
        for offer in payload["offers"]:
            label = offer.get("label")
            if label in by_label and by_label[label]:
                offer["text"] = by_label[label]
        return payload

    def _offer_repair_context(self, payload: dict, invalid: list[dict]) -> dict:
        return {
            "title": payload.get("title"),
            "topic": payload.get("topic"),
            "scenario": payload.get("scenario"),
            "invalid_offers": invalid,
            "profiles": payload.get("profiles", []),
            "answers": payload.get("answers", []),
        }

    def _annotate_offer_lengths(self, payload: dict) -> None:
        offers = {}
        overall_status = "ideal"
        for offer in payload["offers"]:
            label = offer["label"]
            current = _utf8_bytes(offer["text"])
            status = (
                "ideal"
                if AUFGABE_1_OFFER_MIN_BYTES <= current <= AUFGABE_1_OFFER_MAX_BYTES
                else "accepted_with_warning"
            )
            if status != "ideal":
                overall_status = "accepted_with_warning"
            offers[label] = {"bytes": current, "status": status}
        payload["length_metadata"] = {
            "target_per_offer_bytes": AUFGABE_1_OFFER_TARGET_BYTES,
            "ideal_range_per_offer_bytes": [AUFGABE_1_OFFER_MIN_BYTES, AUFGABE_1_OFFER_MAX_BYTES],
            "hard_range_per_offer_bytes": [
                AUFGABE_1_OFFER_HARD_MIN_BYTES,
                AUFGABE_1_OFFER_HARD_MAX_BYTES,
            ],
            "status": overall_status,
            "offers": offers,
        }


class ReadingAufgabe2Generator(BaseReadingGenerator):
    """生成 TestDaF 阅读第二题：三选一选择题。"""

    def generate(self, api_key: str, data: ReadingAufgabe2Input) -> dict:
        payload = self._call_generation(api_key, self._system_prompt(), self._user_prompt(data), 8000)
        payload = self._normalize_long_text_payload(payload, min_paragraphs=5)
        payload = self._repair_long_text_length(
            api_key=api_key,
            payload=payload,
            task_label="阅读第二题",
            target_bytes=AUFGABE_2_TARGET_BYTES,
            ideal_min_bytes=AUFGABE_2_MIN_BYTES,
            ideal_max_bytes=AUFGABE_2_MAX_BYTES,
            hard_min_bytes=AUFGABE_2_HARD_MIN_BYTES,
            hard_max_bytes=AUFGABE_2_HARD_MAX_BYTES,
            min_paragraphs=5,
        )
        self._validate(payload)
        self._annotate_text_length(payload)
        return payload

    def _system_prompt(self) -> str:
        return (
            "你是 TestDaF Leseverstehen 出题专家，负责生成阅读第二题 Lesetext 2 的完整结构化物料。"
            "Lesetext 2 是一篇中长说明文、科普文或社会现象分析文本，后接 10 道 A/B/C 三选一题，题号 11-20。"
            "该题考查细节定位、因果理解、比较、研究过程、限制条件、作者结论和整体理解。"
            "题目应基本跟随文本顺序，最后可设置整体结论题。干扰项应来自细节偷换、程度变化、因果误读或范围扩大。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "顶层字段必须包含 title、topic、reading_text、paragraphs、questions。"
            "paragraphs 必须包含 5-8 个段落，每段应有相对完整的论述功能。"
            "reading_text 必须能由 paragraphs 按顺序拼接还原，不要让 reading_text 与 paragraphs 内容不一致。"
            "reading_text 的 UTF-8 byte length 目标约 4103，理想范围 3900-4300。"
        )

    def _user_prompt(self, data: ReadingAufgabe2Input) -> str:
        reference = data.reference_material or "无额外参考素材。"
        length_hint = {
            "short": "约 3900-4100 UTF-8 bytes",
            "long": "约 4100-4300 UTF-8 bytes",
        }.get(data.text_length, "目标约 4103 UTF-8 bytes，理想范围 3900-4300")
        return (
            "请生成 TestDaF Leseverstehen Lesetext 2 三选一选择题。\n\n"
            f"- 说明文主题：{data.topic}\n"
            f"- 参考素材：{reference}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 文本长度：{length_hint}\n"
            f"- 技能侧重：{data.skill_focus}\n\n"
            "篇幅硬性要求：reading_text 的 UTF-8 byte length 目标约 4103，理想范围 3900-4300；"
            "如果需要，请通过增加或压缩解释、例子、研究细节来贴近该长度。\n\n"
            "文本应具有清晰段落结构，内容可涉及科学、城市生态、学习心理、技术社会影响或健康研究。"
            "段落要求：必须生成 5-8 个 paragraphs；每个段落 80-160 词左右；"
            "每段承担不同功能，例如背景、问题、研究/例子、原因、影响、限制、结论。"
            "请输出 JSON：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "topic": "主题",\n'
            '  "reading_text": "完整德语阅读文本",\n'
            '  "paragraphs": [{"index": 1, "text": "段落"}],\n'
            '  "questions": [{"number": 11, "prompt": "题干", "options": {"A": "...", "B": "...", "C": "..."}, "answer": "A", "evidence": "依据", "tested_skill": "detail/cause/comparison/conclusion", "distractor_explanation": "干扰项说明"}]\n'
            "}\n"
        )

    def _validate(self, payload: dict) -> None:
        for key in ("title", "topic", "reading_text", "paragraphs", "questions"):
            if key not in payload:
                raise RuntimeError(f"阅读第二题生成结果缺少字段：{key}")
        if not isinstance(payload["paragraphs"], list) or len(payload["paragraphs"]) < 5:
            raise RuntimeError("阅读第二题至少需要 5 个段落")
        self._validate_text_length(payload["reading_text"])
        questions = payload["questions"]
        if not isinstance(questions, list) or len(questions) != 10:
            raise RuntimeError("阅读第二题必须生成 10 道题")
        for index, question in enumerate(questions, start=11):
            if question.get("number") != index:
                question["number"] = index
            options = question.get("options")
            if not isinstance(options, dict) or set(options.keys()) != {"A", "B", "C"}:
                raise RuntimeError(f"第 {index} 题必须包含 A/B/C 三个选项")
            if question.get("answer") not in {"A", "B", "C"}:
                raise RuntimeError(f"第 {index} 题答案必须是 A、B 或 C")
            for key in ("prompt", "evidence", "tested_skill", "distractor_explanation"):
                if key not in question:
                    raise RuntimeError(f"第 {index} 题缺少字段：{key}")

    def _validate_text_length(self, reading_text: str) -> None:
        current = _utf8_bytes(reading_text)
        if current < AUFGABE_2_HARD_MIN_BYTES or current > AUFGABE_2_HARD_MAX_BYTES:
            raise RuntimeError(
                f"阅读第二题 reading_text UTF-8 长度目标约 {AUFGABE_2_TARGET_BYTES} bytes，"
                f"硬范围为 {AUFGABE_2_HARD_MIN_BYTES}-{AUFGABE_2_HARD_MAX_BYTES} bytes，"
                f"当前为 {current} bytes"
            )

    def _annotate_text_length(self, payload: dict) -> None:
        current = _utf8_bytes(payload["reading_text"])
        status = "ideal" if AUFGABE_2_MIN_BYTES <= current <= AUFGABE_2_MAX_BYTES else "accepted_with_warning"
        payload["length_metadata"] = {
            "target_bytes": AUFGABE_2_TARGET_BYTES,
            "ideal_range_bytes": [AUFGABE_2_MIN_BYTES, AUFGABE_2_MAX_BYTES],
            "hard_range_bytes": [AUFGABE_2_HARD_MIN_BYTES, AUFGABE_2_HARD_MAX_BYTES],
            "current_bytes": current,
            "status": status,
        }


class ReadingAufgabe3Generator(BaseReadingGenerator):
    """生成 TestDaF 阅读第三题：Ja/Nein/Text sagt dazu nichts。"""

    def generate(self, api_key: str, data: ReadingAufgabe3Input) -> dict:
        payload = self._call_generation(api_key, self._system_prompt(), self._user_prompt(data), 8500)
        payload = self._normalize_long_text_payload(payload, min_paragraphs=5)
        payload = self._repair_long_text_length(
            api_key=api_key,
            payload=payload,
            task_label="阅读第三题",
            target_bytes=AUFGABE_3_TARGET_BYTES,
            ideal_min_bytes=AUFGABE_3_MIN_BYTES,
            ideal_max_bytes=AUFGABE_3_MAX_BYTES,
            hard_min_bytes=AUFGABE_3_HARD_MIN_BYTES,
            hard_max_bytes=AUFGABE_3_HARD_MAX_BYTES,
            min_paragraphs=5,
        )
        self._validate(payload)
        self._annotate_text_length(payload)
        return payload

    def _system_prompt(self) -> str:
        return (
            "你是 TestDaF Leseverstehen 出题专家，负责生成阅读第三题 Lesetext 3 的完整结构化物料。"
            "Lesetext 3 是较长的学术、文化、社会或科学主题文章，后接 10 道 Ja/Nein/Text sagt dazu nichts 判断题，题号 21-30。"
            "该题难度高于 Lesetext 2，核心是区分原文支持、原文明示相反、以及原文没有提供信息。"
            "Nein 必须与原文明确矛盾；Text sagt dazu nichts 必须是真的未提及，不能只是表达隐晦。"
            "你必须只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "顶层字段必须包含 title、topic、reading_text、paragraphs、statements。"
            "paragraphs 必须包含 5-8 个段落，每段信息密度高但逻辑清楚。"
            "reading_text 必须能由 paragraphs 按顺序拼接还原，不要让 reading_text 与 paragraphs 内容不一致。"
            "reading_text 的 UTF-8 byte length 目标约 4963，理想范围 4700-5200。"
        )

    def _user_prompt(self, data: ReadingAufgabe3Input) -> str:
        reference = data.reference_material or "无额外参考素材。"
        return (
            "请生成 TestDaF Leseverstehen Lesetext 3 判断题。\n\n"
            f"- 学术/社会文化主题：{data.topic}\n"
            f"- 参考素材：{reference}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 判断项分布：{data.judgement_balance}\n"
            f"- 未提及项强化：{data.unsupported_items}\n\n"
            "篇幅硬性要求：reading_text 的 UTF-8 byte length 目标约 4963，理想范围 4700-5200；"
            "如果需要，请通过增加或压缩背景、论证、例子、限制条件和结论来贴近该长度。\n\n"
            "文本应有较高信息密度，包含背景、问题、原因、措施、例子、限制和结论。"
            "段落要求：必须生成 5-8 个 paragraphs；每个段落 90-170 词左右；"
            "每段承担不同论述功能，并为判断题提供清晰证据边界。"
            "请输出 JSON：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "topic": "主题",\n'
            '  "reading_text": "完整德语阅读文本",\n'
            '  "paragraphs": [{"index": 1, "text": "段落"}],\n'
            '  "statements": [{"number": 21, "statement": "判断陈述", "answer": "Ja", "evidence": "依据或未提及说明", "tested_information": "考查点", "judgement_type": "supported/contradicted/not_given", "explanation": "解释"}]\n'
            "}\n"
        )

    def _validate(self, payload: dict) -> None:
        for key in ("title", "topic", "reading_text", "paragraphs", "statements"):
            if key not in payload:
                raise RuntimeError(f"阅读第三题生成结果缺少字段：{key}")
        if not isinstance(payload["paragraphs"], list) or len(payload["paragraphs"]) < 5:
            raise RuntimeError("阅读第三题至少需要 5 个段落")
        self._validate_text_length(payload["reading_text"])
        statements = payload["statements"]
        if not isinstance(statements, list) or len(statements) != 10:
            raise RuntimeError("阅读第三题必须生成 10 道判断题")
        valid = {"Ja", "Nein", "Text sagt dazu nichts"}
        seen = set()
        for index, statement in enumerate(statements, start=21):
            if statement.get("number") != index:
                statement["number"] = index
            answer = statement.get("answer")
            if answer not in valid:
                raise RuntimeError(f"第 {index} 题答案必须是 Ja、Nein 或 Text sagt dazu nichts")
            seen.add(answer)
            for key in ("statement", "evidence", "tested_information", "judgement_type", "explanation"):
                if key not in statement:
                    raise RuntimeError(f"第 {index} 题缺少字段：{key}")
        if len(seen) < 3:
            raise RuntimeError("阅读第三题必须同时包含 Ja、Nein 和 Text sagt dazu nichts")

    def _validate_text_length(self, reading_text: str) -> None:
        current = _utf8_bytes(reading_text)
        if current < AUFGABE_3_HARD_MIN_BYTES or current > AUFGABE_3_HARD_MAX_BYTES:
            raise RuntimeError(
                f"阅读第三题 reading_text UTF-8 长度目标约 {AUFGABE_3_TARGET_BYTES} bytes，"
                f"硬范围为 {AUFGABE_3_HARD_MIN_BYTES}-{AUFGABE_3_HARD_MAX_BYTES} bytes，"
                f"当前为 {current} bytes"
            )

    def _annotate_text_length(self, payload: dict) -> None:
        current = _utf8_bytes(payload["reading_text"])
        status = "ideal" if AUFGABE_3_MIN_BYTES <= current <= AUFGABE_3_MAX_BYTES else "accepted_with_warning"
        payload["length_metadata"] = {
            "target_bytes": AUFGABE_3_TARGET_BYTES,
            "ideal_range_bytes": [AUFGABE_3_MIN_BYTES, AUFGABE_3_MAX_BYTES],
            "hard_range_bytes": [AUFGABE_3_HARD_MIN_BYTES, AUFGABE_3_HARD_MAX_BYTES],
            "current_bytes": current,
            "status": status,
        }
