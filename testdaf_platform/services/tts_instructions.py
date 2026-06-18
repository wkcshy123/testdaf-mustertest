"""为听力对话的每个发言片段生成 TTS 表现力指令。

Qwen-TTS 的 ``instructions`` 用自然语言控制语速、语气、情绪、语调、
角色感等。本服务在对话文案生成之后、TTS 合成之前，作为中间步骤：
综合场景、说话人身份、对话走向，为每个 segment 产出一条对应的
中文 instruction，让合成语音更接近真实对话。
"""

from __future__ import annotations

import json

from testdaf_platform.config import QWEN_TEXT_MODEL
from testdaf_platform.services.generation_utils import parse_json
from testdaf_platform.services.text_generation import TextGenerationClient

# instructions 最大约 1600 token；每条指令留足余量。
MAX_INSTRUCTION_CHARS = 120
# 对所有 segments 一起做整体长度保护（粗安全网，防异常超长输出）。
# 单条 ~120 中文字符，按最多 ~30 段对话估算。
MAX_INSTRUCTION_BYTES = 16000


class InstructionGenerationError(RuntimeError):
    """指令生成结果无法解析或字段不完整。"""


class InstructionGenerator:
    """为对话 segments 逐段生成 Qwen-TTS 表现力指令。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL, client: TextGenerationClient | None = None):
        self.model = model
        self.client = client or TextGenerationClient(model=model)

    def generate(
        self,
        *,
        api_key: str,
        title: str,
        scenario: str,
        speaker_roles: dict[str, str],
        relationship: str,
        segments: list[dict],
        speech_speed: str = "normal",
    ) -> list[str]:
        """返回与 ``segments`` 等长、一一对应的 instruction 字符串列表。"""
        n = len(segments)
        if n == 0:
            return []

        content = self.client.generate_text(
            api_key=api_key,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": self._user_prompt(
                        title=title,
                        scenario=scenario,
                        speaker_roles=speaker_roles,
                        relationship=relationship,
                        segments=segments,
                        speech_speed=speech_speed,
                    ),
                },
            ],
            max_tokens=2000,
        )
        parsed = parse_json(content)
        instructions = self._extract_instructions(parsed, n)
        self._validate_instructions(instructions, n)
        return instructions

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _system_prompt(self) -> str:
        return (
            "你是语音合成表现力导演。给定一段德语对话的全部片段、说话人身份与场景，"
            "你要为每个片段（每个说话人的连续发言）写一条 Qwen-TTS 的 instruction，"
            "用自然中文控制这条发言的语速、语气、情绪、语调与角色感，使合成语音像真实对话。\n"
            "要求：\n"
            "- 必须只输出合法 JSON，不要 Markdown、解释或代码块。\n"
            "- 顶层是一个对象，包含字段 \"instructions\"，它是一个数组，"
            "长度与输入 segments 完全相同，顺序一一对应。\n"
            "- 数组元素是字符串，必须是中文，单条不超过约 120 字。\n"
            "- 每条指令应明确：语速（慢/中/快）+ 语气（亲切/专业/热情/温柔等）"
            "+ 情绪（平稳/开心/坚定/略带紧张等）+ 角色或场景，可点出该句的语气重点。\n"
            "- 同一说话人的不同发言可以根据上下文变化语气色彩（亲切↔严肃↔好奇），"
            "但音量和音高须保持前后一致；不能出现音量陡升陡降。"
            "同一说话人声线应自然连贯，像同一个人的声音在说话。\n"
            "- 提问者通常更口语、略带好奇；提供信息/规则的一方更清晰、稳重。\n"
            "- 对话衔接必须自然，两个说话人之间不能有抢话感；"
            "如果当前发言是回应或确认，衔接语速应略缓半拍再自然过渡。\n"
            "- 不要给任何 segment 写'语速很快'的指令，除非该发言明确表示急切、紧张或催促。\n"
            "- 如果发言文本中包含感叹词如 Ach!、Oh!、Na ja...，请在 instruction 中用相应的语气描述，"
            "例如'带着叹息说'、'略带惊讶'、'语气迟疑'。"
            "不要提示跳过这些词。\n"
            "- 不要改写德语文本内容，只描述如何朗读。\n"
            "- speech_speed 会给出整体语速倾向，请据此调整每条指令中的语速描述。\n"
            "- 全文必须用德语语音朗读。如果该段文本包含容易被误读为英语的德语词"
            "（如 Germanistik、Anglistik、Romanistik、Slawistik、Skandinavistik 等学科名称、"
            "Handy（手机）、Event（活动）、Ticket 等），"
            "请在指令末尾注明'用德语发音朗读所有词汇，"
            "尤其注意 Germanistik/Anglistik/Handy 等词不要读成英语'。\n"
            "- 德语日常英语借词 Job、Team、Computer、Laptop、Meeting、Smartphone、Workshop 维持英语发音，"
            "不需要特别标注。"
        )

    def _user_prompt(
        self,
        *,
        title: str,
        scenario: str,
        speaker_roles: dict[str, str],
        relationship: str,
        segments: list[dict],
        speech_speed: str,
    ) -> str:
        speed_hint = {
            "slow": "整体语速偏慢，便于考生听懂。",
            "fast": "整体语速偏快，接近真实母语者自然语速。",
        }.get(speech_speed, "整体语速适中，自然清晰。")

        compact_segments = [
            {
                "index": s.get("index", i + 1),
                "speaker_id": s.get("speaker_id", ""),
                "speaker_role": s.get("speaker_role", ""),
                "text": s.get("text", ""),
                "pause_reason": s.get("pause_reason", ""),
            }
            for i, s in enumerate(segments)
        ]

        return (
            f"对话标题：{title or '（无）'}\n"
            f"场景：{scenario or '（无）'}\n"
            f"说话人身份：{json.dumps(speaker_roles, ensure_ascii=False)}\n"
            f"关系：{relationship or '（无）'}\n"
            f"语速要求：{speed_hint}\n"
            f"重要：输入中 speaker_id 相同的 segment 是同一个人说话，"
            f"务必保持其声线、音量和音高前后一致。\n\n"
            "对话片段（按播放顺序）：\n"
            f"{json.dumps(compact_segments, ensure_ascii=False, indent=2)}\n\n"
            f"请为以上 {len(compact_segments)} 个片段各生成一条中文 instruction。\n"
            "只输出 JSON：\n"
            "{\n"
            '  "instructions": [\n'
            '    "第一条指令",\n'
            '    "..."\n'
            "  ]\n"
            "}"
        )

    # ------------------------------------------------------------------
    # Parsing / validation
    # ------------------------------------------------------------------

    def _extract_instructions(self, parsed: object, expected_len: int) -> list[str]:
        if isinstance(parsed, dict):
            instructions = parsed.get("instructions")
        elif isinstance(parsed, list):
            instructions = parsed
        else:
            instructions = None

        if not isinstance(instructions, list):
            raise InstructionGenerationError("指令生成结果缺少 instructions 数组")

        result: list[str] = []
        for item in instructions[:expected_len]:
            text = str(item).strip() if item is not None else ""
            if len(text) > MAX_INSTRUCTION_CHARS:
                text = text[:MAX_INSTRUCTION_CHARS]
            result.append(text)

        # 若模型返回数量不足，补默认指令，避免阻塞 TTS。
        if len(result) < expected_len:
            result.extend([""] * (expected_len - len(result)))
        return result

    def _validate_instructions(self, instructions: list[str], expected_len: int) -> None:
        if len(instructions) != expected_len:
            raise InstructionGenerationError(
                f"指令数量不匹配：期望 {expected_len}，得到 {len(instructions)}"
            )
        total_bytes = sum(len(ins.encode("utf-8")) for ins in instructions)
        if total_bytes > MAX_INSTRUCTION_BYTES:
            raise InstructionGenerationError(
                f"指令总字节过长：{total_bytes} > {MAX_INSTRUCTION_BYTES}"
            )
