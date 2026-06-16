import unittest

from testdaf_platform.services.tts_instructions import (
    InstructionGenerationError,
    InstructionGenerator,
)
from testdaf_platform.usecases._instruction_support import attach_instructions_to_segments


class _FakeClient:
    """Stand-in for TextGenerationClient returning canned JSON."""

    def __init__(self, content: str):
        self._content = content
        self.calls = []

    def generate_text(self, *, api_key, messages, max_tokens=None):
        self.calls.append(messages)
        return self._content


def _make_segments(n: int = 3) -> list[dict]:
    return [
        {
            "index": i + 1,
            "speaker_id": "A" if i % 2 == 0 else "B",
            "speaker_role": "Studierende_r" if i % 2 == 0 else "Mitarbeiter_in",
            "text": f"Dialogbeitrag Nummer {i + 1}.",
            "pause_after_ms": 350,
            "pause_reason": "normal_turn_switch",
        }
        for i in range(n)
    ]


class InstructionGeneratorTest(unittest.TestCase):
    def test_generate_returns_one_instruction_per_segment(self):
        payload = '{"instructions": ["语速中等，语气亲切，略带好奇，像学生提问。", "语速中等偏慢，语气专业稳重，清晰说明规则，句尾平稳。", "语速中等，语气轻松自然，情绪略开心。"]}'
        gen = InstructionGenerator(client=_FakeClient(payload))

        instructions = gen.generate(
            api_key="fake-key",
            title="Bibliothek",
            scenario="学生咨询图书馆规则",
            speaker_roles={"A": "Studierende_r", "B": "Mitarbeiter_in"},
            relationship="Kunde_Betreuer_in",
            segments=_make_segments(3),
            speech_speed="normal",
        )

        self.assertEqual(len(instructions), 3)
        self.assertTrue(all(isinstance(s, str) and s for s in instructions))
        self.assertIn("亲切", instructions[0])

    def test_generate_accepts_top_level_list(self):
        payload = '["指令一", "指令二"]'
        gen = InstructionGenerator(client=_FakeClient(payload))

        instructions = gen.generate(
            api_key="fake-key",
            title="t",
            scenario="s",
            speaker_roles={"A": "x", "B": "y"},
            relationship="r",
            segments=_make_segments(2),
        )
        self.assertEqual(instructions, ["指令一", "指令二"])

    def test_generate_strips_markdown_fence(self):
        payload = '```json\n{"instructions": ["指令甲", "指令乙"]}\n```'
        gen = InstructionGenerator(client=_FakeClient(payload))
        instructions = gen.generate(
            api_key="fake-key",
            title="t",
            scenario="s",
            speaker_roles={"A": "x", "B": "y"},
            relationship="r",
            segments=_make_segments(2),
        )
        self.assertEqual(instructions, ["指令甲", "指令乙"])

    def test_generate_pads_when_model_returns_too_few(self):
        payload = '{"instructions": ["只有一条"]}'
        gen = InstructionGenerator(client=_FakeClient(payload))
        instructions = gen.generate(
            api_key="fake-key",
            title="t",
            scenario="s",
            speaker_roles={"A": "x", "B": "y"},
            relationship="r",
            segments=_make_segments(3),
        )
        self.assertEqual(len(instructions), 3)
        self.assertEqual(instructions[0], "只有一条")
        self.assertEqual(instructions[1], "")

    def test_generate_truncates_overlong_instruction(self):
        long_one = "语" * 200
        payload = f'{{"instructions": ["{long_one}", "短"]}}'
        gen = InstructionGenerator(client=_FakeClient(payload))
        instructions = gen.generate(
            api_key="fake-key",
            title="t",
            scenario="s",
            speaker_roles={"A": "x", "B": "y"},
            relationship="r",
            segments=_make_segments(2),
        )
        self.assertEqual(len(instructions[0]), 120)

    def test_generate_empty_segments_returns_empty(self):
        gen = InstructionGenerator(client=_FakeClient(""))
        self.assertEqual(gen.generate(api_key="k", title="", scenario="", speaker_roles={}, relationship="", segments=[]), [])

    def test_generate_raises_on_missing_instructions_key(self):
        gen = InstructionGenerator(client=_FakeClient('{"foo": []}'))
        with self.assertRaises(InstructionGenerationError):
            gen.generate(
                api_key="k",
                title="t",
                scenario="s",
                speaker_roles={"A": "x", "B": "y"},
                relationship="r",
                segments=_make_segments(2),
            )


class AttachInstructionsTest(unittest.TestCase):
    def test_attaches_instruction_to_each_segment(self):
        segments = _make_segments(2)
        attach_instructions_to_segments(segments, ["指令A", "指令B"])
        self.assertEqual(segments[0]["tts_instruction"], "指令A")
        self.assertEqual(segments[1]["tts_instruction"], "指令B")

    def test_strips_and_handles_empty(self):
        segments = _make_segments(2)
        attach_instructions_to_segments(segments, ["  带空格  ", ""])
        self.assertEqual(segments[0]["tts_instruction"], "带空格")
        self.assertEqual(segments[1]["tts_instruction"], "")

    def test_raises_on_length_mismatch(self):
        segments = _make_segments(3)
        with self.assertRaises(RuntimeError):
            attach_instructions_to_segments(segments, ["只有一条"])


if __name__ == "__main__":
    unittest.main()
