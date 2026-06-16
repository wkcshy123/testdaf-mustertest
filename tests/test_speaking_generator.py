import json
import unittest

from testdaf_platform.services.speaking import (
    SpeakingTaskGenerator,
    SpeakingTaskInput,
)


class FakeTextGenerationClient:
    """Records calls and returns canned JSON, proving generate() routes through it."""

    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.calls: list[dict] = []

    def generate_text(self, *, api_key, messages, max_tokens=None) -> str:
        self.calls.append({"api_key": api_key, "messages": messages})
        return self.raw_text


def _valid_payload_json() -> str:
    return json.dumps(
        {
            "title": "Telefonische Beratung",
            "scenario": "Sie rufen beim International Office an, um sich nach Sprachkursen zu erkundigen.",
            "prompt_points": [
                "Stellen Sie sich vor und nennen Sie Ihr Anliegen.",
                "Fragen Sie nach den Kurszeiten und den Gebühren.",
                "Bedanken Sie sich höflich am Ende des Gesprächs.",
            ],
            "examiner_intro": "Guten Tag, hier ist das International Office. Wie kann ich Ihnen heute helfen?",
            "chart_specs": [],
        },
        ensure_ascii=False,
    )


class SpeakingTaskGeneratorTest(unittest.TestCase):
    def test_generate_routes_through_text_generation_client(self) -> None:
        generator = SpeakingTaskGenerator()
        fake_client = FakeTextGenerationClient(_valid_payload_json())
        generator.client = fake_client  # inject fake, bypass real API

        payload = generator.generate(
            api_key="fake-key",
            data=SpeakingTaskInput(
                number=1,
                topic="Sprachkurse am International Office",
                reference_material="",
                image_notes="",
                difficulty="standard",
                examiner_role="Mitarbeiterin",
                voice="Cherry",
            ),
        )

        # The client must have been called exactly once with the api_key.
        self.assertEqual(len(fake_client.calls), 1)
        self.assertEqual(fake_client.calls[0]["api_key"], "fake-key")

        # multimodal content (list of dicts) is passed through verbatim.
        message = fake_client.calls[0]["messages"][0]
        self.assertEqual(message["role"], "user")
        self.assertIsInstance(message["content"], list)

        # Returned payload is parsed and enriched with task metadata.
        self.assertEqual(payload["title"], "Telefonische Beratung")
        self.assertEqual(payload["number"], 1)
        self.assertEqual(payload["needs_chart"], False)
        self.assertEqual(payload["voice"], "Cherry")


if __name__ == "__main__":
    unittest.main()
