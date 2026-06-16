"""TestDaF 口语题生成服务。"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from testdaf_platform.config import QWEN_TEXT_MODEL
from testdaf_platform.services.text_generation import TextGenerationClient


TASK_PROFILES = {
    1: {
        "name": "电话咨询/信息询问",
        "description": "校园或日常服务电话场景，考生需要说明来意、询问课程/预约/服务细节。",
        "exam_focus": "自我介绍、说明来意、询问具体信息",
        "prep_time": "30 Sekunden",
        "speaking_time": "30 Sekunden",
        "needs_chart": False,
    },
    2: {
        "name": "本国情况说明",
        "description": "同学或朋友询问考生本国情况，考生需要介绍经验、现状或已有措施。",
        "exam_focus": "说明个人经验、本国情况和已有措施",
        "prep_time": "1 Minute",
        "speaking_time": "1 Minute",
        "needs_chart": False,
    },
    3: {
        "name": "图表描述",
        "description": "基于一张图表描述趋势、比例或群体差异，重点训练客观数据表达。",
        "exam_focus": "描述图表结构、概括信息、比较趋势或群体",
        "prep_time": "1 Minute",
        "speaking_time": "1 Minute 30 Sekunden",
        "needs_chart": True,
    },
    4: {
        "name": "议题立场表达",
        "description": "围绕较复杂的社会、学习或科技议题表达立场，并用理由和例子支撑观点。",
        "exam_focus": "权衡利弊、表达赞成或反对、说明理由",
        "prep_time": "3 Minuten",
        "speaking_time": "2 Minuten",
        "needs_chart": False,
    },
    5: {
        "name": "学习/人生决策建议",
        "description": "朋友面临学习、专业、大学或职业选择，考生需要给出建议并权衡利弊。",
        "exam_focus": "给朋友建议、权衡利弊、说明理由",
        "prep_time": "2 Minuten",
        "speaking_time": "1 Minute 30 Sekunden",
        "needs_chart": False,
    },
    6: {
        "name": "图表 + 原因/影响分析",
        "description": "先使用图表信息，再进一步解释可能原因、社会影响或未来发展。",
        "exam_focus": "使用图表信息，解释原因并分析影响",
        "prep_time": "3 Minuten",
        "speaking_time": "2 Minuten",
        "needs_chart": True,
    },
    7: {
        "name": "复杂生活化选择建议",
        "description": "具体生活场景中的选择题，例如出行、住宿或活动安排，考生需要比较条件并给建议。",
        "exam_focus": "在具体生活场景中做选择、比较条件、给出建议",
        "prep_time": "1 Minute 30 Sekunden",
        "speaking_time": "1 Minute 30 Sekunden",
        "needs_chart": False,
    },
}


@dataclass(frozen=True)
class SpeakingTaskInput:
    number: int
    topic: str
    reference_material: str
    image_notes: str
    difficulty: str
    examiner_role: str
    voice: str
    chart_count: int = 1
    chart_types: list[str] | None = None
    reference_image_paths: list[Path] | None = None


class SpeakingTaskGenerator:
    """生成单道 TestDaF Mündlicher Ausdruck 题目。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model
        self.client = TextGenerationClient(model=model)

    def generate(self, api_key: str, data: SpeakingTaskInput) -> dict:
        profile = TASK_PROFILES[data.number]
        expected_chart_count = max(1, min(data.chart_count, 2)) if profile["needs_chart"] else 0
        content = self._build_content(data, profile)
        raw_text = self.client.generate_text(
            api_key=api_key,
            messages=[{"role": "user", "content": content}],
        )
        payload = self._parse_json(raw_text)
        self._validate(payload, data.number, profile, expected_chart_count)
        payload["number"] = data.number
        payload["task_type"] = profile["name"]
        payload["prep_time"] = profile["prep_time"]
        payload["speaking_time"] = profile["speaking_time"]
        payload["needs_chart"] = profile["needs_chart"]
        payload["examiner_role"] = data.examiner_role
        payload["voice"] = data.voice
        return payload

    def _build_content(self, data: SpeakingTaskInput, profile: dict) -> list[dict]:
        content = [{"image": f"file://{path.resolve()}"} for path in (data.reference_image_paths or [])]
        content.append({"text": self._prompt(data, profile)})
        return content

    def _prompt(self, data: SpeakingTaskInput, profile: dict) -> str:
        image_instruction = (
            "已提供本地参考图片。请理解图片中的图表、数据或场景信息，并将其转化为题目材料。"
            if data.reference_image_paths
            else "未提供参考图片。"
        )
        chart_count = max(1, min(data.chart_count, 2))
        chart_types = (data.chart_types or [])[:chart_count]
        if len(chart_types) < chart_count:
            chart_types += ["mixed"] * (chart_count - len(chart_types))
        type_labels = {"bar": "柱状图", "line": "折线图", "pie": "比例图", "mixed": "自动"}
        chart_spec_examples = []
        for i in range(chart_count):
            ct = chart_types[i]
            if ct == "mixed":
                chart_spec_examples.append(
                    f'    {{"type": "bar", "title": "图表{i + 1}标题", "unit": "单位", '
                    f'"source_note": "Quelle: ...", "data": [{{"label": "A", "value": 10}}]}}'
                )
            else:
                chart_spec_examples.append(
                    f'    {{"type": "{ct}", "title": "图表{i + 1}标题", "unit": "单位", '
                    f'"source_note": "Quelle: ...", "data": [{{"label": "A", "value": 10}}]}}'
                )
        if profile["needs_chart"]:
            chart_schema = '  "chart_specs": [\n' + ",\n".join(chart_spec_examples) + "\n  ],\n"
            type_hints = []
            for i, ct in enumerate(chart_types):
                if ct != "mixed":
                    type_hints.append(f"图表 {i + 1} 必须是 {type_labels.get(ct, ct)}")
            type_note = "；".join(type_hints)
            chart_requirement = (
                f"本题必须生成 {chart_count} 张图表，chart_specs 长度必须为 {chart_count}。"
                f"图表 type 只能是 bar、line 或 pie。"
                + (f" {type_note}。" if type_note else "")
                + "图表数据要服务于口语题中的描述、原因或影响分析。\n"
            )
        else:
            chart_schema = '  "chart_specs": [],\n'
            chart_requirement = "本题不需要图表，chart_specs 必须为空数组。\n"
        return (
            "你是 TestDaF Mündlicher Ausdruck 出题专家，负责生成单道口语题。"
            "题目必须贴近德国大学生活、学习、社会讨论或日常沟通场景。"
            "生成内容只用于题目本身，不要生成答案、评分标准或范例回答。\n\n"
            f"题号：Aufgabe {data.number}\n"
            f"题型：{profile['name']}\n"
            f"考查重点：{profile['exam_focus']}\n"
            f"准备时间：{profile['prep_time']}\n"
            f"回答时间：{profile['speaking_time']}\n"
            f"主题：{data.topic}\n"
            f"参考素材：{data.reference_material or '无额外参考素材。'}\n"
            f"图片说明：{data.image_notes or '无额外图片说明。'}\n"
            f"难度：{data.difficulty}\n"
            f"发问者角色：{data.examiner_role}\n"
            f"{image_instruction}\n\n"
            f"{chart_requirement}"
            "生成要求：\n"
            "- scenario 用德语写，简短说明考生所处情境和要做什么。\n"
            "- prompt_points 用德语写 2-4 条，必须是考生回答要点。\n"
            "- examiner_intro 用德语写，是发问者在准备时间后对考生说的简短引子，必须只写 1-2 句话，适合 TTS。\n"
            "- examiner_intro 要符合角色身份，直接邀请考生开始回答，禁止添加背景解释或过长铺垫。\n"
            "- Aufgabe 7 必须是具体生活化选择建议场景，不要写成抽象政策题。\n\n"
            "请只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。结构如下：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "scenario": "德语情境描述",\n'
            '  "prompt_points": ["回答要点 1", "回答要点 2"],\n'
            '  "examiner_intro": "发问者引子台词",\n'
            f"{chart_schema}"
            '  "source_note": "素材使用说明，内部字段"\n'
            "}\n"
        )

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
                raise RuntimeError("无法从 API 响应中解析口语题 JSON")
            return json.loads(match.group(0))

    def _validate(self, payload: dict, number: int, profile: dict, expected_chart_count: int) -> None:
        for key in ("title", "scenario", "prompt_points", "examiner_intro", "chart_specs"):
            if key not in payload:
                raise RuntimeError(f"口语 Aufgabe {number} 生成结果缺少字段：{key}")
        points = payload["prompt_points"]
        if not isinstance(points, list) or len(points) < 2:
            raise RuntimeError(f"口语 Aufgabe {number} 至少需要 2 个回答要点")
        intro = str(payload["examiner_intro"]).strip()
        if len(intro) < 20:
            raise RuntimeError(f"口语 Aufgabe {number} 引子语音文本过短")
        charts = payload["chart_specs"]
        if profile["needs_chart"]:
            if not isinstance(charts, list) or len(charts) != expected_chart_count:
                raise RuntimeError(f"口语 Aufgabe {number} 必须生成 {expected_chart_count} 张图表")
            for chart in charts:
                self._validate_chart(chart, number)
        elif charts:
            payload["chart_specs"] = []

    def _validate_chart(self, chart: dict, number: int) -> None:
        if chart.get("type") not in {"bar", "line", "pie"}:
            chart["type"] = "bar"
        for key in ("title", "unit", "source_note", "data"):
            if key not in chart:
                raise RuntimeError(f"口语 Aufgabe {number} 图表缺少字段：{key}")
        data = chart["data"]
        if not isinstance(data, list) or len(data) < 3:
            raise RuntimeError(f"口语 Aufgabe {number} 图表至少需要 3 个数据点")
        for item in data:
            if "label" not in item or "value" not in item:
                raise RuntimeError(f"口语 Aufgabe {number} 图表数据点必须包含 label 和 value")
            item["value"] = float(item["value"])
