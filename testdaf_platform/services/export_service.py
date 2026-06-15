"""题库导出服务 — Word + PDF。"""

import json
import re
from pathlib import Path

from docx import Document
from docx.shared import Cm, Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from fpdf import FPDF

from testdaf_platform.config import PROJECT_ROOT
from testdaf_platform.storage.question_bank import QuestionBank

DOWNLOADS_DIR = PROJECT_ROOT / "downloads"

_ARIAL_TTF = Path("C:/Windows/Fonts/arial.ttf")
_ARIALBD_TTF = Path("C:/Windows/Fonts/arialbd.ttf")
_FONT_CANDIDATES = [
    (_ARIAL_TTF, _ARIALBD_TTF),
    (Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")),
    (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf")),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")),
]

_SECTION_LABELS = {
    "listening": "Hörverstehen",
    "reading": "Leseverstehen",
    "writing": "Schriftlicher Ausdruck",
    "speaking": "Mündlicher Ausdruck",
}


def safe_filename(title: str, max_len: int = 50) -> str:
    name = re.sub(r'[<>:\"/\\|?*]', "", title)
    name = re.sub(r"\s+", "_", name.strip())
    if len(name) <= max_len:
        return name
    words = re.findall(r"[A-Za-zÄÖÜäöüß]{3,}", title)
    result = "_".join(words)
    if len(result) > max_len:
        result = result[:max_len].rstrip("_")
    return result if result else name[:max_len]


def _first_existing_font() -> tuple[Path, Path] | None:
    for regular, bold in _FONT_CANDIDATES:
        if regular.exists():
            return regular, bold if bold.exists() else regular
    return None


def _latin_safe(value: object) -> str:
    replacements = {
        "—": "-",
        "–": "-",
        "‑": "-",
        "“": '"',
        "”": '"',
        "„": '"',
        "’": "'",
        "‘": "'",
        "…": "...",
    }
    text = str(value)
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


class ExportService:

    def __init__(self, bank: QuestionBank | None = None):
        self.bank = bank or QuestionBank()

    def export(self, relative_path: str, fmt: str = "docx") -> Path:
        bundle = self.bank.load_question_bundle(relative_path)
        if fmt == "docx":
            return self._export_docx(bundle)
        return self._export_pdf(bundle)

    # ── dispatch ──────────────────────────────────────────────

    def _export_docx(self, bundle: dict) -> Path:
        manifest = bundle["manifest"]
        section = manifest.get("section", "")
        task_type = manifest.get("task_type", "")
        title = manifest.get("title", "Export")

        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(11)
        style.paragraph_format.space_after = Pt(6)

        _add_docx_header(doc, _SECTION_LABELS.get(section, section), task_type)

        if section == "reading":
            self._docx_reading(doc, bundle, task_type)
        elif section == "listening":
            self._docx_listening(doc, bundle)
        elif section == "writing":
            self._docx_writing(doc, bundle)
        elif section == "speaking":
            self._docx_speaking(doc, bundle)

        return _save_docx(doc, title)

    def _export_pdf(self, bundle: dict) -> Path:
        manifest = bundle["manifest"]
        section = manifest.get("section", "")
        task_type = manifest.get("task_type", "")
        title = manifest.get("title", "Export")

        pdf = _PdfBuilder()
        pdf.add_header(_SECTION_LABELS.get(section, section), task_type)

        if section == "reading":
            self._pdf_reading(pdf, bundle, task_type)
        elif section == "listening":
            self._pdf_listening(pdf, bundle)
        elif section == "writing":
            self._pdf_writing(pdf, bundle)
        elif section == "speaking":
            self._pdf_speaking(pdf, bundle)

        return _save_pdf(pdf, title)

    # ── Reading ───────────────────────────────────────────────

    def _docx_reading(self, doc, bundle: dict, task_type: str) -> None:
        if task_type == "aufgabe_1":
            self._docx_reading_a1(doc, bundle)
        elif task_type == "aufgabe_2":
            self._docx_reading_a2(doc, bundle)
        elif task_type == "aufgabe_3":
            self._docx_reading_a3(doc, bundle)

    def _docx_reading_a1(self, doc, bundle: dict) -> None:
        manifest = bundle["manifest"]
        profiles = bundle.get("profiles", [])
        offers = bundle.get("texts", [])
        example_label = manifest.get("parameters", {}).get("example_offer_label")
        scenario = _extract_scenario(bundle, "reading", "aufgabe_1")

        doc.add_heading("Aufgabenstellung", level=2)
        if scenario:
            doc.add_paragraph(scenario)
        else:
            doc.add_paragraph(
                "Sie suchen für verschiedene Personen eine passende Anzeige. "
                "Schreiben Sie den jeweiligen Buchstaben (A–H). "
                "Wenn es keine passende Anzeige gibt, schreiben Sie I."
            )
        doc.add_paragraph("")

        doc.add_heading("Personen 1 – 10", level=2)
        for p in profiles:
            doc.add_paragraph(f"{p['number']}.  {p['need']}")

        doc.add_page_break()
        doc.add_heading("Texte A – H", level=2)
        for offer in _practice_offers(offers, example_label):
            heading = f"{offer['label']}.  {offer.get('heading', '')}"
            p = doc.add_paragraph()
            p.add_run(heading).bold = True
            doc.add_paragraph(offer.get("text", ""))
        _docx_add_example_offer(doc, offers, example_label)

    def _docx_reading_a2(self, doc, bundle: dict) -> None:
        reading_text = bundle.get("reading_text", "")
        paragraphs_list = bundle.get("paragraphs", [])
        questions = bundle.get("questions", [])

        if paragraphs_list:
            for p_item in paragraphs_list:
                doc.add_paragraph(p_item.get("text", ""))
                doc.add_paragraph("")
        elif reading_text:
            doc.add_paragraph(reading_text)

        doc.add_page_break()
        doc.add_heading("Aufgaben 11 – 20", level=2)
        for q in questions:
            p = doc.add_paragraph()
            p.add_run(f"{q['number']}.  {q.get('prompt', '')}").bold = True
            opts = q.get("options", {})
            for label in ("A", "B", "C"):
                doc.add_paragraph(f"    {label}    {opts.get(label, '')}")
            doc.add_paragraph("")

    def _docx_reading_a3(self, doc, bundle: dict) -> None:
        reading_text = bundle.get("reading_text", "")
        paragraphs_list = bundle.get("paragraphs", [])
        statements = bundle.get("statements", []) or bundle.get("questions", [])

        if paragraphs_list:
            for p_item in paragraphs_list:
                doc.add_paragraph(p_item.get("text", ""))
                doc.add_paragraph("")
        elif reading_text:
            doc.add_paragraph(reading_text)

        doc.add_page_break()
        doc.add_heading("Aufgaben 21 – 30: Ja / Nein / Text sagt dazu nichts", level=2)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        for i, h in enumerate(["Nr.", "Aussage", "Ja", "Nein", "TSN"]):
            cell = table.rows[0].cells[i]
            cell.text = h
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
        for s in statements:
            row = table.add_row()
            row.cells[0].text = str(s.get("number", ""))
            row.cells[1].text = s.get("statement", "")
            row.cells[2].text = ""
            row.cells[3].text = ""
            row.cells[4].text = ""

    def _pdf_reading(self, pdf: "_PdfBuilder", bundle: dict, task_type: str) -> None:
        if task_type == "aufgabe_1":
            self._pdf_reading_a1(pdf, bundle)
        elif task_type == "aufgabe_2":
            self._pdf_reading_a2(pdf, bundle)
        elif task_type == "aufgabe_3":
            self._pdf_reading_a3(pdf, bundle)

    def _pdf_reading_a1(self, pdf: "_PdfBuilder", bundle: dict) -> None:
        manifest = bundle["manifest"]
        profiles = bundle.get("profiles", [])
        offers = bundle.get("texts", [])
        example_label = manifest.get("parameters", {}).get("example_offer_label")
        scenario = _extract_scenario(bundle, "reading", "aufgabe_1")
        pdf.add_heading("Aufgabenstellung")
        pdf.add_text(scenario or "Schreiben Sie den jeweiligen Buchstaben (A–H).")
        pdf.ln(4)
        pdf.add_heading("Personen 1 – 10")
        for p in profiles:
            pdf.add_text(f"{p['number']}.  {p['need']}")
            pdf.ln(1)
        pdf.add_page()
        pdf.add_heading("Texte A – H")
        for offer in _practice_offers(offers, example_label):
            pdf.add_subheading(f"{offer['label']}.  {offer.get('heading', '')}")
            pdf.add_text(offer.get("text", ""))
            pdf.ln(3)
        _pdf_add_example_offer(pdf, offers, example_label)

    def _pdf_reading_a2(self, pdf: "_PdfBuilder", bundle: dict) -> None:
        paragraphs_list = bundle.get("paragraphs", [])
        reading_text = bundle.get("reading_text", "")
        questions = bundle.get("questions", [])
        if paragraphs_list:
            for p_item in paragraphs_list:
                pdf.add_text(p_item.get("text", ""))
                pdf.ln(3)
        elif reading_text:
            pdf.add_text(reading_text)
        pdf.add_page()
        pdf.add_heading("Aufgaben 11 – 20")
        for q in questions:
            pdf.add_bold(f"{q['number']}.  {q.get('prompt', '')}")
            opts = q.get("options", {})
            for label in ("A", "B", "C"):
                pdf.add_text(f"    {label}    {opts.get(label, '')}")
            pdf.ln(2)

    def _pdf_reading_a3(self, pdf: "_PdfBuilder", bundle: dict) -> None:
        paragraphs_list = bundle.get("paragraphs", [])
        reading_text = bundle.get("reading_text", "")
        statements = bundle.get("statements", []) or bundle.get("questions", [])
        if paragraphs_list:
            for p_item in paragraphs_list:
                pdf.add_text(p_item.get("text", ""))
                pdf.ln(3)
        elif reading_text:
            pdf.add_text(reading_text)
        pdf.add_page()
        pdf.add_heading("Aufgaben 21 – 30: Ja / Nein / TSN")
        col_w = [12, 110, 18, 20, 18]
        pdf.add_table_row(col_w, ["Nr.", "Aussage", "Ja", "Nein", "TSN"], bold=True)
        for s in statements:
            pdf.add_table_row(col_w, [
                str(s.get("number", "")),
                s.get("statement", "")[:180],
                "", "", "",
            ])

    # ── Listening ─────────────────────────────────────────────

    def _docx_listening(self, doc, bundle: dict) -> None:
        transcript = bundle.get("transcript", "")
        questions = bundle.get("questions", []) or bundle.get("statements", [])

        doc.add_heading("Aufgaben", level=2)
        for q in questions:
            num = q.get("number", "")
            prompt = q.get("prompt") or q.get("statement", "")
            doc.add_paragraph(f"{num}.  {prompt}")

        doc.add_page_break()
        doc.add_heading("Transkript", level=2)
        doc.add_paragraph(transcript)

    def _pdf_listening(self, pdf: "_PdfBuilder", bundle: dict) -> None:
        transcript = bundle.get("transcript", "")
        questions = bundle.get("questions", []) or bundle.get("statements", [])
        pdf.add_heading("Aufgaben")
        for q in questions:
            num = q.get("number", "")
            prompt = q.get("prompt") or q.get("statement", "")
            pdf.add_text(f"{num}.  {prompt}")
            pdf.ln(2)
        pdf.add_page()
        pdf.add_heading("Transkript")
        pdf.add_text(transcript)

    # ── Writing ───────────────────────────────────────────────

    def _docx_writing(self, doc, bundle: dict) -> None:
        prompt_data = bundle.get("prompt", {})
        background = prompt_data.get("background", "") or prompt_data.get("topic", "")
        task_prompt = prompt_data.get("task_prompt", "")
        instructions = prompt_data.get("writing_instructions", [])

        if background:
            doc.add_paragraph(background)
            doc.add_paragraph("")
        doc.add_heading("Aufgabe", level=2)
        p = doc.add_paragraph()
        p.add_run(task_prompt).bold = True
        doc.add_paragraph("")
        doc.add_heading("Bearbeiten Sie die folgenden Punkte:", level=2)
        for instr in instructions:
            doc.add_paragraph(instr, style="List Number")
        _docx_add_chart_specs(doc, bundle.get("charts", []))

    def _pdf_writing(self, pdf: "_PdfBuilder", bundle: dict) -> None:
        prompt_data = bundle.get("prompt", {})
        background = prompt_data.get("background", "") or prompt_data.get("topic", "")
        task_prompt = prompt_data.get("task_prompt", "")
        instructions = prompt_data.get("writing_instructions", [])
        if background:
            pdf.add_text(background)
            pdf.ln(4)
        pdf.add_heading("Aufgabe")
        pdf.add_bold(task_prompt)
        pdf.ln(4)
        pdf.add_heading("Bearbeiten Sie die folgenden Punkte:")
        for instr in instructions:
            pdf.add_text(f"- {instr}")
        _pdf_add_chart_specs(pdf, bundle.get("charts", []))

    # ── Speaking ──────────────────────────────────────────────

    def _docx_speaking(self, doc, bundle: dict) -> None:
        manifest = bundle.get("manifest", {})
        if manifest.get("task_type") == "test_set":
            tasks = bundle.get("tasks", [])
            for i, task in enumerate(tasks):
                self._docx_speaking_task(doc, task)
                if i < len(tasks) - 1:
                    doc.add_page_break()
        else:
            generation = bundle.get("prompt", {})
            self._docx_speaking_task(doc, generation)

    def _docx_speaking_task(self, doc, task: dict) -> None:
        num = task.get("number", "")
        task_label = task.get("task_type", "")
        prep = task.get("prep_time", "")
        speak = task.get("speaking_time", "")
        scenario = task.get("scenario", "")
        points = task.get("prompt_points", [])
        examiner_role = task.get("examiner_role", "")
        examiner_intro = task.get("examiner_intro", "")

        doc.add_heading(f"Aufgabe {num}: {task_label}", level=2)
        line = f"Vorbereitungszeit: {prep}"
        if speak:
            line += f"  |  Sprechzeit: {speak}"
        if examiner_role:
            line += f"  |  Gesprächspartner/in: {examiner_role}"
        doc.add_paragraph(line)
        doc.add_heading("Situation", level=3)
        doc.add_paragraph(scenario)
        doc.add_heading("Ihre Aufgabe", level=3)
        for point in points:
            doc.add_paragraph(point, style="List Number")
        if examiner_intro:
            doc.add_heading("Gesprächsimpuls", level=3)
            p = doc.add_paragraph()
            p.add_run(f"„{examiner_intro}“").italic = True
        _docx_add_chart_specs(doc, task.get("chart_specs", []))

    def _pdf_speaking(self, pdf: "_PdfBuilder", bundle: dict) -> None:
        manifest = bundle.get("manifest", {})
        if manifest.get("task_type") == "test_set":
            tasks = bundle.get("tasks", [])
            for i, task in enumerate(tasks):
                self._pdf_speaking_task(pdf, task)
                if i < len(tasks) - 1:
                    pdf.add_page()
        else:
            generation = bundle.get("prompt", {})
            self._pdf_speaking_task(pdf, generation)

    def _pdf_speaking_task(self, pdf: "_PdfBuilder", task: dict) -> None:
        num = task.get("number", "")
        task_label = task.get("task_type", "")
        prep = task.get("prep_time", "")
        speak = task.get("speaking_time", "")
        scenario = task.get("scenario", "")
        points = task.get("prompt_points", [])
        examiner_role = task.get("examiner_role", "")

        pdf.add_heading(f"Aufgabe {num}: {task_label}")
        line = f"Vorbereitungszeit: {prep}"
        if speak:
            line += f"  |  Sprechzeit: {speak}"
        if examiner_role:
            line += f"  |  Gesprächspartner/in: {examiner_role}"
        pdf.add_text(line)
        pdf.ln(3)
        pdf.add_subheading("Situation")
        pdf.add_text(scenario)
        pdf.ln(3)
        pdf.add_subheading("Ihre Aufgabe")
        for point in points:
            pdf.add_text(f"- {point}")
        _pdf_add_chart_specs(pdf, task.get("chart_specs", []))


# ── helpers ──────────────────────────────────────────────────

def _practice_offers(offers: list[dict], example_label: str | None) -> list[dict]:
    if not example_label:
        return offers
    return [offer for offer in offers if offer.get("label") != example_label]


def _find_offer(offers: list[dict], label: str | None) -> dict | None:
    if not label:
        return None
    return next((offer for offer in offers if offer.get("label") == label), None)


def _docx_add_example_offer(doc, offers: list[dict], example_label: str | None) -> None:
    example = _find_offer(offers, example_label)
    if not example:
        return
    doc.add_page_break()
    doc.add_heading(f"Beispieltext {example_label}", level=2)
    p = doc.add_paragraph()
    p.add_run(f"{example['label']}.  {example.get('heading', '')}").bold = True
    doc.add_paragraph(example.get("text", ""))


def _pdf_add_example_offer(pdf: "_PdfBuilder", offers: list[dict], example_label: str | None) -> None:
    example = _find_offer(offers, example_label)
    if not example:
        return
    pdf.add_page()
    pdf.add_heading(f"Beispieltext {example_label}")
    pdf.add_subheading(f"{example['label']}.  {example.get('heading', '')}")
    pdf.add_text(example.get("text", ""))


def _docx_add_chart_specs(doc, chart_specs: list[dict]) -> None:
    if not chart_specs:
        return
    doc.add_heading("Grafiken", level=2)
    for index, chart in enumerate(chart_specs, start=1):
        doc.add_heading(f"Grafik {index}: {chart.get('title', 'Grafik')}", level=3)
        meta = []
        if chart.get("unit"):
            meta.append(f"Einheit: {chart['unit']}")
        if chart.get("source_note"):
            meta.append(str(chart["source_note"]))
        if meta:
            doc.add_paragraph(" · ".join(meta))
        data = chart.get("data", [])
        if data:
            table = doc.add_table(rows=1, cols=2)
            table.style = "Table Grid"
            table.rows[0].cells[0].text = "Label"
            table.rows[0].cells[1].text = "Wert"
            for item in data:
                row = table.add_row()
                row.cells[0].text = str(item.get("label", ""))
                row.cells[1].text = str(item.get("value", ""))


def _pdf_add_chart_specs(pdf: "_PdfBuilder", chart_specs: list[dict]) -> None:
    if not chart_specs:
        return
    pdf.add_heading("Grafiken")
    for index, chart in enumerate(chart_specs, start=1):
        pdf.add_subheading(f"Grafik {index}: {chart.get('title', 'Grafik')}")
        meta = []
        if chart.get("unit"):
            meta.append(f"Einheit: {chart['unit']}")
        if chart.get("source_note"):
            meta.append(str(chart["source_note"]))
        if meta:
            pdf.add_text(" · ".join(meta))
            pdf.ln(1)
        data = chart.get("data", [])
        if data:
            pdf.add_table_row([90, 35], ["Label", "Wert"], bold=True)
            for item in data:
                pdf.add_table_row([90, 35], [str(item.get("label", ""))[:60], str(item.get("value", ""))])
            pdf.ln(3)


def _extract_scenario(bundle: dict, section: str, task_type: str) -> str:
    preview = bundle.get("preview", "")
    if not preview:
        return ""
    for line in preview.splitlines():
        line = line.strip()
        if line.startswith("### Aufgabenstellung") or line.startswith("**Aufgabenstellung"):
            continue
        if line and not line.startswith("#") and not line.startswith("*") and len(line) > 30:
            return line
    return ""


def _save_docx(doc: Document, title: str) -> Path:
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(title)}.docx"
    path = DOWNLOADS_DIR / filename
    doc.save(str(path))
    return path


def _save_pdf(pdf: "_PdfBuilder", title: str) -> Path:
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(title)}.pdf"
    path = DOWNLOADS_DIR / filename
    pdf.output(str(path))
    return path


def _add_docx_header(doc: Document, section: str, task_type: str) -> None:
    label = task_type.replace("_", " ").title()
    h = doc.add_heading(f"{section}  —  {label}", level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("")


# ── PDF builder ──────────────────────────────────────────────

class _PdfBuilder:

    def __init__(self):
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=20)
        self.pdf.add_page()
        self._init_fonts()

    def _init_fonts(self) -> None:
        font_pair = _first_existing_font()
        self.uses_unicode_font = font_pair is not None
        if font_pair:
            regular, bold = font_pair
            self.pdf.add_font("F0", "", str(regular))
            self.pdf.add_font("F0", "B", str(bold))
            self.font = "F0"
            self.font_bold = "F0"
        else:
            self.font = "Helvetica"
            self.font_bold = "Helvetica"

    def _text(self, value: object) -> str:
        text = str(value)
        return text if self.uses_unicode_font else _latin_safe(text)

    def add_header(self, section: str, task_type: str) -> None:
        label = task_type.replace("_", " ").title()
        self.pdf.set_font(self.font_bold, size=16)
        self.pdf.cell(0, 12, self._text(f"{section}  —  {label}"), ln=True, align="C")
        self.pdf.ln(6)

    def add_heading(self, text: str) -> None:
        self.pdf.set_font(self.font_bold, size=13)
        self.pdf.cell(0, 9, self._text(text), ln=True)
        self.pdf.ln(3)

    def add_subheading(self, text: str) -> None:
        self.pdf.set_font(self.font_bold, size=10.5)
        self.pdf.cell(0, 7, self._text(text), ln=True)
        self.pdf.ln(1)

    def add_text(self, text: str) -> None:
        self.pdf.set_font(self.font, size=10)
        self.pdf.multi_cell(self.pdf.epw, 5.2, self._text(text))

    def add_bold(self, text: str) -> None:
        self.pdf.set_font(self.font_bold, size=10)
        self.pdf.multi_cell(self.pdf.epw, 5.2, self._text(text))

    def add_table_row(self, col_widths: list, values: list[str], bold: bool = False) -> None:
        font = self.font_bold if bold else self.font
        self.pdf.set_font(font, size=9)
        for i, val in enumerate(values):
            self.pdf.cell(col_widths[i], 7, self._text(val), border=1)
        self.pdf.ln()

    def add_page(self) -> None:
        self.pdf.add_page()

    def ln(self, h: int = 0) -> None:
        self.pdf.ln(h)

    def output(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(path)
