"""Run real DashScope text-generation probes for request-shape debugging."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testdaf_platform.services.config_store import ConfigStore
from testdaf_platform.services.listening_aufgabe_1 import (
    ListeningAufgabe1Generator,
    ListeningAufgabe1Input,
)
from testdaf_platform.services.reading import ReadingAufgabe1Generator, ReadingAufgabe1Input
from testdaf_platform.services.text_generation import TextGenerationClient


@dataclass(frozen=True)
class ProbeCase:
    name: str
    model: str
    messages: list[dict]
    max_tokens: int


def _business_reading_messages() -> list[dict]:
    data = ReadingAufgabe1Input(
        topic="大学校园服务与学习支持",
        reference_material="学习咨询、写作中心、语言伙伴项目、心理咨询、图书馆培训、IT 服务台、职业中心、奖学金咨询",
        difficulty="standard",
        offer_count=8,
        no_match_count=3,
    )
    generator = ReadingAufgabe1Generator()
    return [
        {"role": "system", "content": generator._system_prompt()},
        {"role": "user", "content": generator._user_prompt(data)},
    ]


def _business_listening_messages() -> list[dict]:
    data = ListeningAufgabe1Input(
        scenario="学生在大学图书馆咨询小组学习室预约、借阅期限、打印服务和安静区规则",
        reference_material=(
            "图书馆小组学习室需要提前在线预约，每次最多两小时。普通图书可借四周，到期前可以续借一次。"
            "打印机位于一楼信息台旁边，学生卡可直接扣费。三楼是安静学习区，不能打电话，也不能进行小组讨论。"
            "新生可以在服务台激活图书馆账户。"
        ),
        difficulty="standard",
        information_flow="sequential",
    )
    generator = ListeningAufgabe1Generator()
    return [
        {"role": "system", "content": generator._system_prompt()},
        {"role": "user", "content": generator._user_prompt(data)},
    ]


def _message_chars(messages: list[dict]) -> int:
    return sum(len(str(message.get("content", ""))) for message in messages)


def _cases(model: str) -> list[ProbeCase]:
    repeated = "校园服务包括学习咨询、写作中心、语言伙伴项目、心理咨询、图书馆培训、IT服务台。" * 80
    reading_messages = _business_reading_messages()
    listening_messages = _business_listening_messages()
    return [
        ProbeCase("user_short_7000", model, [{"role": "user", "content": "请只回复 OK"}], 7000),
        ProbeCase(
            "system_user_short_7000",
            model,
            [{"role": "system", "content": "你是助手。"}, {"role": "user", "content": "请只回复 OK"}],
            7000,
        ),
        ProbeCase(
            "system_user_long_simple_1000",
            model,
            [
                {"role": "system", "content": "你是结构化出题助手，只输出 JSON。"},
                {"role": "user", "content": "请基于以下信息生成简短 JSON：" + repeated},
            ],
            1000,
        ),
        ProbeCase("reading_business_1000", model, reading_messages, 1000),
        ProbeCase("reading_business_3000", model, reading_messages, 3000),
        ProbeCase("reading_business_7000", model, reading_messages, 7000),
        ProbeCase("listening_business_3000", model, listening_messages, 3000),
        ProbeCase("listening_business_4000", model, listening_messages, 4000),
        ProbeCase("listening_business_5000", model, listening_messages, 5000),
        ProbeCase("listening_business_6000", model, listening_messages, 6000),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.7-plus")
    parser.add_argument("--case", default="", help="Run only cases whose name contains this value.")
    args = parser.parse_args()

    api_key = ConfigStore().load_api_key()
    if not api_key:
        print("API_KEY_AVAILABLE=no")
        return 2

    print("API_KEY_AVAILABLE=yes")
    print(f"MODEL={args.model}")
    client = TextGenerationClient(model=args.model)
    for case in _cases(args.model):
        if args.case and args.case not in case.name:
            continue
        print(
            f"CASE={case.name} chars={_message_chars(case.messages)} max_tokens={case.max_tokens}",
            flush=True,
        )
        try:
            text = client.generate_text(
                api_key=api_key,
                messages=case.messages,
                max_tokens=case.max_tokens,
            )
            print(f"RESULT=ok length={len(text)} preview={text[:120]!r}", flush=True)
        except Exception as exc:
            print(f"RESULT=error type={type(exc).__name__} message={str(exc)[:500]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
