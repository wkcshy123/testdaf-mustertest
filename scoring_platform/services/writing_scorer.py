from __future__ import annotations

import json
import re
from pathlib import Path

from testdaf_platform.config import CONFIG_FILE, QWEN_TEXT_MODEL, DASHSCOPE_BASE_URL
from testdaf_platform.services.text_generation import TextGenerationClient
from scoring_platform.config import DIMENSION_LABELS


def _load_api_key() -> str:
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                return json.load(f).get("api_key", "")
        except Exception:
            return ""
    return ""


def _extract_student_text(attempt_meta: dict, answers: dict | list) -> str:
    if isinstance(answers, dict):
        for v in answers.values():
            if isinstance(v, str) and len(v) > 50:
                return v
    if isinstance(answers, list):
        for v in answers:
            if isinstance(v, str) and len(v) > 50:
                return v
    return ""


def _extract_writing_prompt(question_id: str) -> str:
    from scoring_platform.config import QUESTION_BANK_DIR
    from shared.file_io.atomic_json import read_json

    for path in QUESTION_BANK_DIR.rglob(question_id):
        if path.is_dir() and ".trash" not in path.parts and (path / "manifest.json").exists():
            manifest = read_json(path / "manifest.json")
            prompts_asset = manifest.get("assets", {}).get("prompt")
            if prompts_asset and (path / prompts_asset).exists():
                prompt_data = read_json(path / prompts_asset)
                if isinstance(prompt_data, str):
                    return prompt_data
                if isinstance(prompt_data, dict):
                    return prompt_data.get("prompt", str(prompt_data))
                if isinstance(prompt_data, list):
                    return "\n".join(str(p) for p in prompt_data)
            return manifest.get("title", "")
    return ""


_PRACTICE_GRADING_PHILOSOPHY = (
    "评分人格说明：你是一个德语写作练习助手，不是考官。你的目标是帮助学生进步。\n"
    "评分原则：\n"
    "- 评分偏向宽容——只要学生大致完成了任务要求，即使有语法或拼写错误，也应给予鼓励性评分。\n"
    "- 对于非母语者的常见偏误（语法小错、拼写错误、介词误用），只要不影响理解，不要因此大幅扣分。\n"
    "- 评语必须以鼓励开头：先热情肯定学生的优点和进步，再温和地指出 1-2 个具体可改进之处。\n"
    "- 建议应具体、可执行（例如'可以尝试用更多从句连接观点'，而非笼统的'需提升语法'）。\n"
    "- TDN 评定时如果处于两个等级之间，请取高不取低。\n"
    "- 整体基调应是'你已经做得很好了，这里有几点可以让你的作文更好'。\n"
)

_EXAM_GRADING_PHILOSOPHY = (
    "评分人格说明：你是 TestDaF 官方评分员，评分严格遵循德福考试标准。\n"
    "评分原则：\n"
    "- 严格按照德福写作评分标准打分，不因是练习而放宽。\n"
    "- 对语法、拼写、结构、内容完成度四大维度进行客观评估。\n"
    "- 评语应客观直接，指出问题，不使用过度鼓励语言。\n"
    "- TDN 评定严格按标准，不游移不偏袒。\n"
)


def score_writing(attempt_meta: dict, answers: dict | list) -> dict | None:
    api_key = _load_api_key()
    if not api_key:
        return {
            "error": "未配置 API Key，无法进行写作评分。请在出题系统中设置。",
            "tdn": 0, "tdn_label": "—",
            "dimensionen": {}, "kommentar": "",
        }

    student_text = _extract_student_text(attempt_meta, answers)
    if not student_text or len(student_text) < 100:
        return {
            "error": "学生作文不足 100 字符，无法评分。",
            "tdn": 0, "tdn_label": "—",
            "dimensionen": {}, "kommentar": "",
        }

    mode = attempt_meta.get("writing_mode", "practice")
    is_exam = mode == "exam"

    question_id = attempt_meta.get("question_id", "")
    prompt_info = _extract_writing_prompt(question_id)

    dim_keys = ["gesamteindruck", "aufgabenbezug", "textaufbau", "satzstrukturen", "wortschatz"]
    dim_list = "\n".join(f"- {DIMENSION_LABELS[k]}" for k in dim_keys)

    philosophy = _EXAM_GRADING_PHILOSOPHY if is_exam else _PRACTICE_GRADING_PHILOSOPHY

    system_prompt = (
        f"{philosophy}\n"
        "请对以下学生作文打分。\n"
        "每个维度按 1（优秀）到 5（不及格）打分。\n"
        "请严格输出如下 JSON（不要 markdown 代码块）：\n"
        "{\n"
        '  "gesamteindruck": 2,\n'
        '  "aufgabenbezug": 2,\n'
        '  "textaufbau": 3,\n'
        '  "satzstrukturen": 3,\n'
        '  "wortschatz": 2,\n'
        '  "tdn": 4,\n'
        '  "tdn_label": "TDN 4",\n'
        '  "kommentar": "请用中文写一段 100-200 字的评语，先肯定优点再指出不足。涉及德语维度名称、术语或例句时保留德语原文。"\n'
        "}\n"
        "评语必须用中文撰写，德语术语/例句保留原文。\n"
        "维度评分参考：1=非常优秀 2=较好 3=一般 4=较弱 5=完全不足\n"
    )

    user_prompt = (
        f"作文题目要求：\n{prompt_info}\n\n"
        f"学生作文正文：\n{student_text}\n\n"
        f"请对以下 {len(dim_keys)} 个维度分别打分 (1-5)：\n{dim_list}"
    )

    client = TextGenerationClient(model=QWEN_TEXT_MODEL, base_url=DASHSCOPE_BASE_URL)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw = client.generate_text(api_key=api_key, messages=messages, max_tokens=1500)
    except Exception as exc:
        return {
            "error": f"LLM 调用失败: {exc}",
            "tdn": 0, "tdn_label": "—",
            "dimensionen": {}, "kommentar": "",
        }

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            result, _ = json.JSONDecoder().raw_decode(cleaned)
            parsed = result
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    parsed = {}
            else:
                parsed = {}

    dimensionen = {}
    for k in dim_keys:
        val = int(parsed.get(k, 3))
        dimensionen[k] = max(1, min(5, val))

    tdn = int(parsed.get("tdn", 0))
    tdn_label = parsed.get("tdn_label", "—")
    kommentar = parsed.get("kommentar", "")

    return {
        "tdn": tdn,
        "tdn_label": tdn_label,
        "dimensionen": dimensionen,
        "kommentar": kommentar,
        "writing_mode": mode,
    }
