import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

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

    def test_retries_transient_network_errors(self) -> None:
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

        with patch(
            "testdaf_platform.services.text_generation.MultiModalConversation.call",
            side_effect=[requests.ConnectionError("reset"), response],
        ) as mm_call:
            with patch("testdaf_platform.services.text_generation.time.sleep") as sleep:
                text = TextGenerationClient(model="qwen3.7-plus").generate_text(
                    api_key="fake-key",
                    messages=[{"role": "user", "content": "请只回复 OK"}],
                    max_tokens=16,
                )

        self.assertEqual(text, "OK")
        self.assertEqual(mm_call.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_falls_back_to_qwen36_flash_after_network_retries(self) -> None:
        fallback_response = SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=[{"text": "OK from fallback"}]),
                    )
                ]
            ),
        )
        call_results = [
            requests.ConnectionError("reset"),
            requests.ConnectionError("reset"),
            requests.ConnectionError("reset"),
            fallback_response,
        ]

        with patch(
            "testdaf_platform.services.text_generation.MultiModalConversation.call",
            side_effect=call_results,
        ) as mm_call:
            with patch("testdaf_platform.services.text_generation.Generation.call") as generation_call:
                with patch("testdaf_platform.services.text_generation.time.sleep"):
                    text = TextGenerationClient(model="qwen3.7-plus").generate_text(
                        api_key="fake-key",
                        messages=[{"role": "user", "content": "请只回复 OK"}],
                        max_tokens=16,
                    )

        self.assertEqual(text, "OK from fallback")
        self.assertEqual(mm_call.call_count, 4)
        self.assertEqual(mm_call.call_args.kwargs["model"], "qwen3.6-flash")
        generation_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
