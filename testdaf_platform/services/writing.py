"""TestDaF 写作题生成服务。"""

import html
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import dashscope

from testdaf_platform.config import DASHSCOPE_BASE_URL, QWEN_TEXT_MODEL
from testdaf_platform.services.text_generation import TextGenerationClient

dashscope.base_http_api_url = DASHSCOPE_BASE_URL

MIN_TASK_BYTES = 1000
MAX_TASK_BYTES = 2200


@dataclass(frozen=True)
class WritingAufgabe1Input:
    topic: str
    reference_material: str
    image_notes: str
    difficulty: str
    chart_count: int
    chart_type_preference: str
    argument_focus: str
    country_comparison: str
    reference_image_paths: list[Path]


class WritingAufgabe1Generator:
    """生成 TestDaF Schriftlicher Ausdruck 写作题。"""

    def __init__(self, model: str = QWEN_TEXT_MODEL):
        self.model = model
        self.client = TextGenerationClient(model=model)

    def generate(self, api_key: str, data: WritingAufgabe1Input) -> dict:
        payload = self._call_generation(api_key, data)
        self._validate(payload, data.chart_count)
        self._annotate_length(payload)
        return payload

    def _call_generation(self, api_key: str, data: WritingAufgabe1Input) -> dict:
        if data.reference_image_paths:
            content = self._build_multimodal_content(data)
            resp = dashscope.MultiModalConversation.call(
                model=self.model,
                api_key=api_key,
                messages=[{"role": "user", "content": content}],
            )
            text = self._extract_multimodal_text(resp)
        else:
            text = self.client.generate_text(
                api_key=api_key,
                messages=[{"role": "user", "content": self._user_prompt(data)}],
                max_tokens=6000,
            )
            return self._parse_json(text)

        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 {resp.status_code}: {resp.message or resp.code}")

        if not text:
            raise RuntimeError("API 未返回写作题内容")
        return self._parse_json(text)

    def _build_multimodal_content(self, data: WritingAufgabe1Input) -> list[dict]:
        content: list[dict] = []
        for path in data.reference_image_paths:
            content.append({"image": f"file://{path.resolve()}"})
        content.append({"text": self._user_prompt(data)})
        return content

    def _extract_multimodal_text(self, response: object) -> str:
        message = response.output.choices[0].message
        content = message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "\n".join(parts).strip()
        return str(content).strip()

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
                raise RuntimeError("无法从 API 响应中解析写作题 JSON")
            return json.loads(match.group(0))

    def _user_prompt(self, data: WritingAufgabe1Input) -> str:
        reference = data.reference_material or "无额外文字或网页参考素材。"
        image_notes = data.image_notes or "无额外图片说明。"
        image_instruction = (
            "已随请求提供本地参考图片。请先理解图片中的主题、数据、图表类型或视觉信息，"
            "再将其转化为适合 TestDaF 写作题的题目描述和图表数据。"
            if data.reference_image_paths
            else "未提供参考图片，请完全根据主题和参考文字生成图表数据。"
        )
        return (
            "你是 TestDaF Schriftlicher Ausdruck 出题专家，负责生成一套完整写作任务。\n"
            "写作题型说明：考生在 60 分钟内围绕一个社会、教育、健康、科技或大学生活议题写一篇连贯论述文；"
            "题目包含较短背景描述、明确讨论问题、若干写作要求，并附 1-2 张图表。"
            "考生需要描述图表、比较关键信息、表达立场、讨论利弊，并可联系自己国家情况。\n\n"
            f"{image_instruction}\n\n"
            f"- 主题领域：{data.topic}\n"
            f"- 文字/网页参考素材：{reference}\n"
            f"- 参考图片说明：{image_notes}\n"
            f"- 难度：{data.difficulty}\n"
            f"- 图表数量：{data.chart_count}\n"
            f"- 图表偏好：{data.chart_type_preference}\n"
            f"- 论证侧重：{data.argument_focus}\n"
            f"- 是否联系自己国家：{data.country_comparison}\n\n"
            "题干篇幅要求：background 和 task_prompt 合计控制在 1000-2200 UTF-8 bytes；"
            "题干应像真实 TestDaF，不要过长，图表承担主要数据输入。\n\n"
            "正式提问要求：task_prompt 必须是一个清晰的德语讨论问题，形式接近 "
            "“Sollten ...?”、“Ist es sinnvoll, ...?” 或 “Welche Rolle sollte ... spielen?”。"
            "writing_instructions 必须生成 5 条左右正式任务要求，不能是教师说明。"
            "这些要求必须根据你生成的 chart_specs 内容来写："
            "第 1 条要求描述图表中的趋势、发展或分布；"
            "第 2 条要求比较图表中的具体群体、年份、类别或两张图之间的关系；"
            "后续要求应包含表明立场并说明理由、讨论该想法的优点和缺点、联系自己国家情况。"
            "不要使用空泛模板，必须提到图表实际主题或数据维度。\n\n"
            "图表要求：chart_specs 必须包含 1-2 个图表。每个图表必须有 type、title、unit、source_note、data。"
            "type 只能是 bar、line 或 pie。bar/line 的 data 格式为："
            "[{\"label\":\"2005\",\"value\":4.8},{\"label\":\"2007\",\"value\":5.5}]；"
            "pie 的 data 格式为：[{\"label\":\"20-29\",\"value\":31}]。"
            "数据应真实可信、适合德语写作描述，但不需要对应真实统计。\n\n"
            "请只输出合法 JSON，不要输出 Markdown、解释、代码块或 JSON 外文字。"
            "文字部分只生成正式题干，不要生成考试说明、评分标准、范文结构、写作策略或教师备注。结构如下：\n"
            "{\n"
            '  "title": "德语标题",\n'
            '  "topic": "主题",\n'
            '  "background": "德语背景描述",\n'
            '  "task_prompt": "Sollten ...?",\n'
            '  "writing_instructions": ["Beschreiben Sie, wie sich ... entwickelt hat.", "Vergleichen Sie auch ...", "Nehmen Sie Stellung ...", "Diskutieren Sie Vorteile und Nachteile ...", "Gehen Sie auch auf die Situation in Ihrem Heimatland ein."],\n'
            '  "chart_specs": [{"type": "bar", "title": "标题", "unit": "单位", "source_note": "Quelle: ...", "data": [{"label": "A", "value": 10}]}],\n'
            '  "image_usage_note": "如何使用参考图片生成题目，如未提供图片则说明未使用。"\n'
            "}\n"
        )

    def _validate(self, payload: dict, chart_count: int) -> None:
        for key in (
            "title",
            "topic",
            "background",
            "task_prompt",
            "writing_instructions",
            "chart_specs",
        ):
            if key not in payload:
                raise RuntimeError(f"写作题生成结果缺少字段：{key}")
        instructions = payload["writing_instructions"]
        if not isinstance(instructions, list) or len(instructions) < 5:
            raise RuntimeError("写作题至少需要 5 条正式任务要求")
        self._validate_instruction_focus(instructions)
        charts = payload["chart_specs"]
        if not isinstance(charts, list) or len(charts) != chart_count:
            raise RuntimeError(f"写作题必须生成 {chart_count} 张图表说明")
        for index, chart in enumerate(charts, start=1):
            self._validate_chart(chart, index)

    def _validate_chart(self, chart: dict, index: int) -> None:
        if chart.get("type") not in {"bar", "line", "pie"}:
            chart["type"] = "bar"
        for key in ("title", "unit", "source_note", "data"):
            if key not in chart:
                raise RuntimeError(f"第 {index} 张图表缺少字段：{key}")
        data = chart["data"]
        if not isinstance(data, list) or len(data) < 3:
            raise RuntimeError(f"第 {index} 张图表至少需要 3 个数据点")
        for item in data:
            if "label" not in item or "value" not in item:
                raise RuntimeError(f"第 {index} 张图表数据点必须包含 label 和 value")
            item["value"] = float(item["value"])

    def _validate_instruction_focus(self, instructions: list[str]) -> None:
        joined = " ".join(str(item).lower() for item in instructions)
        if not any(keyword in joined for keyword in ("beschreib", "grafik", "entwickl", "verlauf")):
            raise RuntimeError("写作题任务要求必须包含图表描述要求")
        if not any(keyword in joined for keyword in ("vergleich", "unterschied", "zahlen", "gruppen", "anteil")):
            raise RuntimeError("写作题任务要求必须包含数据或群体比较要求")
        if not any(keyword in joined for keyword in ("stellung", "meinung", "begründen", "position")):
            raise RuntimeError("写作题任务要求必须包含表明立场并说明理由的要求")

    def _annotate_length(self, payload: dict) -> None:
        current = len((payload["background"] + "\n" + payload["task_prompt"]).encode("utf-8"))
        payload["length_metadata"] = {
            "task_text_bytes": current,
            "ideal_range_bytes": [MIN_TASK_BYTES, MAX_TASK_BYTES],
            "status": "ideal" if MIN_TASK_BYTES <= current <= MAX_TASK_BYTES else "accepted_with_warning",
        }


class ChartRenderer:
    """将 LLM 生成的图表规格渲染为本地 SVG。"""

    def render_charts(self, chart_specs: list[dict], output_dir: Path) -> list[str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        filenames = []
        for index, spec in enumerate(chart_specs, start=1):
            svg = self.render(spec)
            filename = f"chart_{index}.svg"
            (output_dir / filename).write_text(svg, encoding="utf-8")
            filenames.append(filename)
        return filenames

    def render(self, spec: dict) -> str:
        chart_type = spec.get("type", "bar")
        if chart_type == "line":
            return self._render_line(spec)
        if chart_type == "pie":
            return self._render_pie(spec)
        return self._render_bar(spec)

    def _render_bar(self, spec: dict) -> str:
        data = spec["data"]
        width, height = 820, 460
        left, top, bottom = 80, 74, 90
        chart_width = width - left - 40
        chart_height = height - top - bottom
        max_value = max(float(item["value"]) for item in data) or 1
        bar_gap = 14
        bar_width = max(24, (chart_width - bar_gap * (len(data) - 1)) / len(data))
        bars = []
        for index, item in enumerate(data):
            value = float(item["value"])
            x = left + index * (bar_width + bar_gap)
            bar_height = chart_height * value / max_value
            y = top + chart_height - bar_height
            bars.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" rx="8" fill="#175c54"/>'
                f'<text x="{x + bar_width / 2:.1f}" y="{height - 52}" text-anchor="middle" font-size="15">{_esc(item["label"])}</text>'
                f'<text x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="14" fill="#1e2528">{value:g}</text>'
            )
        return self._svg_shell(spec, width, height, "".join(bars), y_axis=True)

    def _render_line(self, spec: dict) -> str:
        data = spec["data"]
        width, height = 820, 460
        left, top, bottom = 80, 74, 90
        chart_width = width - left - 40
        chart_height = height - top - bottom
        max_value = max(float(item["value"]) for item in data) or 1
        step = chart_width / max(1, len(data) - 1)
        points = []
        labels = []
        for index, item in enumerate(data):
            value = float(item["value"])
            x = left + index * step
            y = top + chart_height - chart_height * value / max_value
            points.append((x, y, value))
            labels.append(
                f'<text x="{x:.1f}" y="{height - 52}" text-anchor="middle" font-size="15">{_esc(item["label"])}</text>'
            )
        polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
        dots = "".join(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#c18f35"/>'
            f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" font-size="14">{value:g}</text>'
            for x, y, value in points
        )
        body = f'<polyline points="{polyline}" fill="none" stroke="#175c54" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>{dots}{"".join(labels)}'
        return self._svg_shell(spec, width, height, body, y_axis=True)

    def _render_pie(self, spec: dict) -> str:
        data = spec["data"]
        width, height = 820, 460
        cx, cy, radius = 270, 250, 130
        total = sum(float(item["value"]) for item in data) or 1
        colors = ["#175c54", "#c18f35", "#8b5e3c", "#487b74", "#d7a84f", "#6d7b88", "#9c6b7d"]
        start = -math.pi / 2
        slices = []
        legend = []
        for index, item in enumerate(data):
            value = float(item["value"])
            angle = value / total * math.tau
            end = start + angle
            large = 1 if angle > math.pi else 0
            x1, y1 = cx + radius * math.cos(start), cy + radius * math.sin(start)
            x2, y2 = cx + radius * math.cos(end), cy + radius * math.sin(end)
            color = colors[index % len(colors)]
            slices.append(
                f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {radius} {radius} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{color}"/>'
            )
            legend_y = 140 + index * 32
            legend.append(
                f'<rect x="500" y="{legend_y - 14}" width="18" height="18" rx="4" fill="{color}"/>'
                f'<text x="530" y="{legend_y}" font-size="16">{_esc(item["label"])}: {value:g}{_esc(spec.get("unit", ""))}</text>'
            )
            start = end
        return self._svg_shell(spec, width, height, "".join(slices + legend), y_axis=False)

    def _svg_shell(self, spec: dict, width: int, height: int, body: str, *, y_axis: bool) -> str:
        axis = ""
        if y_axis:
            axis = (
                '<line x1="80" y1="74" x2="80" y2="370" stroke="#70777a" stroke-width="2"/>'
                '<line x1="80" y1="370" x2="780" y2="370" stroke="#70777a" stroke-width="2"/>'
            )
        title_lines = self._wrap_title(spec.get("title", "Grafik"), width - 80, font_size=22)
        title_elements = []
        title_y = 40
        for line in title_lines:
            title_elements.append(
                f'<text x="40" y="{title_y}" font-size="22" font-weight="700" fill="#1e2528">{_esc(line)}</text>'
            )
            title_y += 28
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            '<rect width="100%" height="100%" rx="22" fill="#fffaf0"/>'
            f'{"".join(title_elements)}'
            f'<text x="40" y="{height - 18}" font-size="13" fill="#70777a">{_esc(spec.get("source_note", ""))}</text>'
            f'<text x="{width - 40}" y="{height - 18}" text-anchor="end" font-size="13" fill="#70777a">Einheit: {_esc(spec.get("unit", ""))}</text>'
            f"{axis}{body}</svg>"
        )

    def _wrap_title(self, title: str, max_width: int, font_size: int) -> list[str]:
        avg_char_width = font_size * 0.58
        max_chars = int(max_width / avg_char_width)
        words = title.split()
        lines = []
        current = []
        for word in words:
            test = " ".join(current + [word])
            if len(test) <= max_chars:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines if lines else [title]


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)
