"""Check DashScope text model availability without exposing the API key.

Usage:
    uv run python scripts/check_dashscope_model.py --model qwen3.7-plus
    uv run python scripts/check_dashscope_model.py --model qwen3.7-plus --compare qwen-plus
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import dashscope

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL
from testdaf_platform.services.config_store import ConfigStore
from testdaf_platform.services.text_generation import TextGenerationClient


@dataclass(frozen=True)
class CheckResult:
    model: str
    base_url: str
    api_mode: str
    status_code: int
    code: str
    message: str
    text_preview: str

    @property
    def ok(self) -> bool:
        return self.status_code == 200


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DashScope model availability.")
    parser.add_argument("--model", default=QWEN_TEXT_MODEL, help="Model name to check.")
    parser.add_argument("--compare", action="append", default=[], help="Additional model to compare.")
    parser.add_argument("--base-url", default=DASHSCOPE_BASE_URL, help="DashScope base HTTP API URL.")
    parser.add_argument("--prompt", default="请只回复 OK", help="Short prompt used for the check.")
    args = parser.parse_args()

    api_key = os.getenv("DASHSCOPE_API_KEY") or ConfigStore().load_api_key()
    if not api_key:
        print("API_KEY_AVAILABLE=no")
        print("请设置 DASHSCOPE_API_KEY，或先在页面保存 API Key。")
        return 2

    print("API_KEY_AVAILABLE=yes")
    models = [args.model, *args.compare]
    results = [check_model(model=model, base_url=args.base_url, api_key=api_key, prompt=args.prompt) for model in models]
    for result in results:
        print_result(result)
    return 0 if results[0].ok else 1


def check_model(*, model: str, base_url: str, api_key: str, prompt: str) -> CheckResult:
    dashscope.base_http_api_url = base_url
    client = TextGenerationClient(model=model, base_url=base_url)
    api_mode = "multimodal-generation" if client.uses_multimodal_api(model) else "text-generation"
    status_code = 200
    code = ""
    message = ""
    text = ""
    try:
        text = client.generate_text(
            api_key=api_key,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16,
        )
    except RuntimeError as exc:
        status_code = 0
        message = str(exc)
    return CheckResult(
        model=model,
        base_url=base_url,
        api_mode=api_mode,
        status_code=status_code,
        code=code,
        message=message,
        text_preview=text[:80],
    )


def print_result(result: CheckResult) -> None:
    print("---")
    print(f"MODEL={result.model}")
    print(f"BASE_URL={result.base_url}")
    print(f"API_MODE={result.api_mode}")
    print(f"STATUS={result.status_code}")
    print(f"OK={'yes' if result.ok else 'no'}")
    if result.code:
        print(f"CODE={result.code}")
    if result.message:
        print(f"MESSAGE={result.message}")
    if result.text_preview:
        print(f"TEXT_PREVIEW={result.text_preview}")


if __name__ == "__main__":
    raise SystemExit(main())
