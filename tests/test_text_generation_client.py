import unittest
from types import SimpleNamespace
from unittest.mock import patch

from testdaf_platform.services.text_generation import TextGenerationClient


class TextGenerationClientTest(unittest.TestCase):
    def test_qwen37_uses_multimodal_api(self) -> None:
        response = SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=[{"text": "OK"}]),
                    )
                ]
            ),
        )

        with patch("testdaf_platform.services.text_generation.MultiModalConversation.call", return_value=response) as mm_call:
            with patch("testdaf_platform.services.text_generation.Generation.call") as generation_call:
                text = TextGenerationClient(model="qwen3.7-plus").generate_text(
                    api_key="fake-key",
                    messages=[{"role": "user", "content": "请只回复 OK"}],
                    max_tokens=16,
                )

        self.assertEqual(text, "OK")
        mm_call.assert_called_once()
        generation_call.assert_not_called()
        sent_messages = mm_call.call_args.kwargs["messages"]
        self.assertEqual(sent_messages[0]["content"], [{"text": "请只回复 OK"}])

    def test_qwen_plus_uses_text_generation_api(self) -> None:
        response = SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(text="OK"),
        )

        with patch("testdaf_platform.services.text_generation.Generation.call", return_value=response) as generation_call:
            with patch("testdaf_platform.services.text_generation.MultiModalConversation.call") as mm_call:
                text = TextGenerationClient(model="qwen-plus").generate_text(
                    api_key="fake-key",
                    messages=[{"role": "user", "content": "请只回复 OK"}],
                    max_tokens=16,
                )

        self.assertEqual(text, "OK")
        generation_call.assert_called_once()
        mm_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
