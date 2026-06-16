"""FastAPI Web 入口。"""

import os
import shutil
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from testdaf_platform.config import COMPLEX_STRUCTURE_MODEL, PROJECT_ROOT, QUESTION_BANK_DIR, VOICES
from testdaf_platform.services.config_store import ConfigStore
from testdaf_platform.services.jobs import JobManager
from testdaf_platform.services.listening_aufgabe_1 import ListeningAufgabe1Generator
from testdaf_platform.services.listening_aufgabe_2 import ListeningAufgabe2Generator
from testdaf_platform.services.listening_aufgabe_3 import ListeningAufgabe3Generator
from testdaf_platform.services.multi_speaker_tts import MultiSpeakerTTSService
from testdaf_platform.services.reading import (
    ReadingAufgabe1Generator,
    ReadingAufgabe2Generator,
    ReadingAufgabe3Generator,
)
from testdaf_platform.services.reference_materials import (
    ReferenceMaterialBundle,
    ReferenceMaterialService,
)
from testdaf_platform.services.speaking import (
    SpeakingTaskGenerator,
    SpeakingTaskInput,
    TASK_PROFILES,
)
from testdaf_platform.services.tts import TTSService
from testdaf_platform.services.writing import (
    ChartRenderer,
    WritingAufgabe1Generator,
)
from testdaf_platform.routers.teacher_manage import create_router as create_teacher_manage_router
from testdaf_platform.routers.teacher_pages import create_router as create_teacher_pages_router
from testdaf_platform.services.export_service import ExportService
from testdaf_platform.storage.question_bank import QuestionBank
from testdaf_platform.usecases.create_listening_aufgabe_1 import (
    CreateListeningAufgabe1Request,
    CreateListeningAufgabe1UseCase,
)
from testdaf_platform.usecases.create_listening_aufgabe_2 import (
    CreateListeningAufgabe2Request,
    CreateListeningAufgabe2UseCase,
)
from testdaf_platform.usecases.create_listening_aufgabe_3 import (
    CreateListeningAufgabe3Request,
    CreateListeningAufgabe3UseCase,
)
from testdaf_platform.usecases.create_reading_aufgabe_1 import (
    CreateReadingAufgabe1Request,
    CreateReadingAufgabe1UseCase,
)
from testdaf_platform.usecases.create_reading_aufgabe_2 import (
    CreateReadingAufgabe2Request,
    CreateReadingAufgabe2UseCase,
)
from testdaf_platform.usecases.create_reading_aufgabe_3 import (
    CreateReadingAufgabe3Request,
    CreateReadingAufgabe3UseCase,
)
from testdaf_platform.usecases.create_writing_aufgabe_1 import (
    CreateWritingAufgabe1Request,
    CreateWritingAufgabe1UseCase,
)

PACKAGE_DIR = Path(__file__).resolve().parent

QUESTION_BANK_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="TestDaF 模拟考试系统", version="0.1.0")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
app.mount("/question-bank", StaticFiles(directory=QUESTION_BANK_DIR), name="question_bank")

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
question_bank = QuestionBank()
export_service = ExportService(question_bank)
config_store = ConfigStore()
aufgabe_1_generator = ListeningAufgabe1Generator()
aufgabe_2_generator = ListeningAufgabe2Generator(model=COMPLEX_STRUCTURE_MODEL)
aufgabe_3_generator = ListeningAufgabe3Generator()
reading_aufgabe_1_generator = ReadingAufgabe1Generator(model=COMPLEX_STRUCTURE_MODEL)
reading_aufgabe_2_generator = ReadingAufgabe2Generator(model=COMPLEX_STRUCTURE_MODEL)
reading_aufgabe_3_generator = ReadingAufgabe3Generator()
writing_aufgabe_1_generator = WritingAufgabe1Generator()
speaking_task_generator = SpeakingTaskGenerator()
chart_renderer = ChartRenderer()
reference_material_service = ReferenceMaterialService()
multi_speaker_tts_service = MultiSpeakerTTSService()
tts_service = TTSService()
job_manager = JobManager(max_workers=3)
create_listening_aufgabe_1_usecase = CreateListeningAufgabe1UseCase(
    reference_material_service=reference_material_service,
    generator=aufgabe_1_generator,
    multi_speaker_tts_service=multi_speaker_tts_service,
    question_bank=question_bank,
)
create_listening_aufgabe_2_usecase = CreateListeningAufgabe2UseCase(
    reference_material_service=reference_material_service,
    generator=aufgabe_2_generator,
    multi_speaker_tts_service=multi_speaker_tts_service,
    question_bank=question_bank,
)
create_listening_aufgabe_3_usecase = CreateListeningAufgabe3UseCase(
    reference_material_service=reference_material_service,
    generator=aufgabe_3_generator,
    multi_speaker_tts_service=multi_speaker_tts_service,
    question_bank=question_bank,
)
create_reading_aufgabe_1_usecase = CreateReadingAufgabe1UseCase(
    reference_material_service=reference_material_service,
    generator=reading_aufgabe_1_generator,
    question_bank=question_bank,
)
create_reading_aufgabe_2_usecase = CreateReadingAufgabe2UseCase(
    reference_material_service=reference_material_service,
    generator=reading_aufgabe_2_generator,
    question_bank=question_bank,
)
create_reading_aufgabe_3_usecase = CreateReadingAufgabe3UseCase(
    reference_material_service=reference_material_service,
    generator=reading_aufgabe_3_generator,
    question_bank=question_bank,
)
create_writing_aufgabe_1_usecase = CreateWritingAufgabe1UseCase(
    reference_material_service=reference_material_service,
    generator=writing_aufgabe_1_generator,
    chart_renderer=chart_renderer,
    question_bank=question_bank,
)

app.include_router(
    create_teacher_manage_router(
        templates=templates,
        question_bank=question_bank,
        export_service=export_service,
    )
)
app.include_router(
    create_teacher_pages_router(
        templates=templates,
        question_bank=question_bank,
        voices=VOICES,
        task_profiles=TASK_PROFILES,
    )
)


@app.on_event("startup")
def startup() -> None:
    question_bank.ensure_layout()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    try:
        return JSONResponse(job_manager.get(job_id))
    except KeyError:
        return JSONResponse({"status": "not_found", "error": "任务不存在"}, status_code=404)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    questions = question_bank.list_questions()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "question_count": len(questions),
            "project_root": PROJECT_ROOT,
        },
    )


@app.post("/teacher/listening/create")
def create_listening_question(
    scenario: str = Form(...),
    reference_material: str = Form(""),
    reference_urls: str = Form(""),
    difficulty: str = Form("standard"),
    information_flow: str = Form("sequential"),
    speed: str = Form("normal"),
    speaker_a_voice: str = Form("Cherry"),
    speaker_b_voice: str = Form("Ethan"),
    api_key: str = Form(""),
) -> RedirectResponse:
    try:
        _resolve_api_key(api_key)
        req = CreateListeningAufgabe1Request(
            scenario=scenario.strip(),
            reference_material=reference_material,
            reference_urls=reference_urls,
            difficulty=difficulty,
            information_flow=information_flow,
            speech_speed=speed,
            speaker_a_voice=speaker_a_voice,
            speaker_b_voice=speaker_b_voice,
        )
        job_id = job_manager.create("听力 Aufgabe 1")

        def run_job() -> str:
            key = _resolve_api_key(api_key)
            job_manager.update(job_id, step="调用文本模型生成对话并合成音频")
            manifest = create_listening_aufgabe_1_usecase.execute(api_key=key, request=req)
            return f"/teacher/listening/aufgabe-1?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/listening/aufgabe-1?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/listening/aufgabe-1?{query}", status_code=303)


@app.post("/teacher/listening/aufgabe-2/create")
def create_listening_aufgabe_2(
    topic: str = Form(...),
    reference_material: str = Form(""),
    reference_urls: str = Form(""),
    difficulty: str = Form("standard"),
    information_flow: str = Form("sequential"),
    statement_balance: str = Form("balanced"),
    speed: str = Form("normal"),
    host_voice: str = Form("Neil"),
    guest_b_voice: str = Form("Maia"),
    guest_c_voice: str = Form("Ethan"),
    api_key: str = Form(""),
) -> RedirectResponse:
    try:
        _resolve_api_key(api_key)
        req = CreateListeningAufgabe2Request(
            topic=topic.strip(),
            reference_material=reference_material,
            reference_urls=reference_urls,
            difficulty=difficulty,
            information_flow=information_flow,
            statement_balance=statement_balance,
            speech_speed=speed,
            host_voice=host_voice,
            guest_b_voice=guest_b_voice,
            guest_c_voice=guest_c_voice,
        )
        job_id = job_manager.create("听力 Aufgabe 2")

        def run_job() -> str:
            key = _resolve_api_key(api_key)
            job_manager.update(job_id, step="调用文本模型生成访谈并合成音频")
            manifest = create_listening_aufgabe_2_usecase.execute(api_key=key, request=req)
            return f"/teacher/listening/aufgabe-2?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/listening/aufgabe-2?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/listening/aufgabe-2?{query}", status_code=303)


@app.post("/teacher/listening/aufgabe-3/create")
def create_listening_aufgabe_3(
    topic: str = Form(...),
    expert_domain: str = Form(...),
    reference_material: str = Form(""),
    reference_urls: str = Form(""),
    difficulty: str = Form("standard"),
    question_focus_mix: str = Form("balanced"),
    multi_point_questions: int = Form(2),
    speed: str = Form("normal"),
    host_voice: str = Form("Neil"),
    expert_voice: str = Form("Maia"),
    api_key: str = Form(""),
) -> RedirectResponse:
    try:
        _resolve_api_key(api_key)
        req = CreateListeningAufgabe3Request(
            topic=topic.strip(),
            expert_domain=expert_domain.strip(),
            reference_material=reference_material,
            reference_urls=reference_urls,
            difficulty=difficulty,
            question_focus_mix=question_focus_mix,
            multi_point_questions=multi_point_questions,
            speech_speed=speed,
            host_voice=host_voice,
            expert_voice=expert_voice,
        )
        job_id = job_manager.create("听力 Aufgabe 3")

        def run_job() -> str:
            key = _resolve_api_key(api_key)
            job_manager.update(job_id, step="调用文本模型生成访谈并合成音频")
            manifest = create_listening_aufgabe_3_usecase.execute(api_key=key, request=req)
            return f"/teacher/listening/aufgabe-3?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/listening/aufgabe-3?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/listening/aufgabe-3?{query}", status_code=303)


@app.post("/teacher/reading/aufgabe-1/create")
def create_reading_aufgabe_1(
    topic: str = Form(...),
    reference_material: str = Form(""),
    reference_urls: str = Form(""),
    difficulty: str = Form("standard"),
    offer_count: int = Form(8),
    no_match_count: int = Form(3),
    api_key: str = Form(""),
) -> RedirectResponse:
    try:
        _resolve_api_key(api_key)
        req = CreateReadingAufgabe1Request(
            topic=topic.strip(),
            reference_material=reference_material,
            reference_urls=reference_urls,
            difficulty=difficulty,
            offer_count=int(offer_count),
            no_match_count=int(no_match_count),
        )
        job_id = job_manager.create("阅读 Aufgabe 1")

        def run_job() -> str:
            key = _resolve_api_key(api_key)
            job_manager.update(job_id, step="调用文本模型生成匹配题")
            manifest = create_reading_aufgabe_1_usecase.execute(api_key=key, request=req)
            return f"/teacher/reading/aufgabe-1?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/reading/aufgabe-1?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/reading/aufgabe-1?{query}", status_code=303)


@app.post("/teacher/reading/aufgabe-2/create")
def create_reading_aufgabe_2(
    topic: str = Form(...),
    reference_material: str = Form(""),
    reference_urls: str = Form(""),
    difficulty: str = Form("standard"),
    text_length: str = Form("standard"),
    skill_focus: str = Form("balanced"),
    api_key: str = Form(""),
) -> RedirectResponse:
    try:
        _resolve_api_key(api_key)
        req = CreateReadingAufgabe2Request(
            topic=topic.strip(),
            reference_material=reference_material,
            reference_urls=reference_urls,
            difficulty=difficulty,
            text_length=text_length,
            skill_focus=skill_focus,
        )
        job_id = job_manager.create("阅读 Aufgabe 2")

        def run_job() -> str:
            key = _resolve_api_key(api_key)
            job_manager.update(job_id, step="调用文本模型生成阅读理解题")
            manifest = create_reading_aufgabe_2_usecase.execute(api_key=key, request=req)
            return f"/teacher/reading/aufgabe-2?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/reading/aufgabe-2?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/reading/aufgabe-2?{query}", status_code=303)


@app.post("/teacher/reading/aufgabe-3/create")
def create_reading_aufgabe_3(
    topic: str = Form(...),
    reference_material: str = Form(""),
    reference_urls: str = Form(""),
    difficulty: str = Form("standard"),
    judgement_balance: str = Form("balanced"),
    unsupported_items: str = Form("standard"),
    api_key: str = Form(""),
) -> RedirectResponse:
    try:
        _resolve_api_key(api_key)
        req = CreateReadingAufgabe3Request(
            topic=topic.strip(),
            reference_material=reference_material,
            reference_urls=reference_urls,
            difficulty=difficulty,
            judgement_balance=judgement_balance,
            unsupported_items=unsupported_items,
        )
        job_id = job_manager.create("阅读 Aufgabe 3")

        def run_job() -> str:
            key = _resolve_api_key(api_key)
            job_manager.update(job_id, step="调用文本模型生成判断题")
            manifest = create_reading_aufgabe_3_usecase.execute(api_key=key, request=req)
            return f"/teacher/reading/aufgabe-3?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/reading/aufgabe-3?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/reading/aufgabe-3?{query}", status_code=303)


@app.post("/teacher/writing/aufgabe-1/create")
def create_writing_aufgabe_1(
    topic: str = Form(...),
    reference_material: str = Form(""),
    reference_urls: str = Form(""),
    image_notes: str = Form(""),
    difficulty: str = Form("standard"),
    chart_count: int = Form(2),
    chart_type_preference: str = Form("mixed"),
    argument_focus: str = Form("balanced"),
    country_comparison: str = Form("required"),
    api_key: str = Form(""),
    reference_images: list[UploadFile] = File(default=[]),
) -> RedirectResponse:
    question_id = question_bank.new_question_id()
    question_dir = question_bank.get_question_dir("writing", "aufgabe_1", question_id)
    try:
        _resolve_api_key(api_key)
        reference_image_files, reference_image_paths = _save_reference_images(
            question_dir,
            reference_images,
        )
        req = CreateWritingAufgabe1Request(
            topic=topic.strip(),
            reference_material=reference_material,
            reference_urls=reference_urls,
            image_notes=image_notes,
            difficulty=difficulty,
            chart_count=chart_count,
            chart_type_preference=chart_type_preference,
            argument_focus=argument_focus,
            country_comparison=country_comparison,
            question_id=question_id,
            reference_image_files=reference_image_files,
            reference_image_paths=reference_image_paths,
        )
        job_id = job_manager.create("写作 Aufgabe 1")

        def run_job() -> str:
            key = _resolve_api_key(api_key)
            job_manager.update(job_id, step="调用文本模型生成写作题并渲染图表")
            manifest = create_writing_aufgabe_1_usecase.execute(api_key=key, request=req)
            return f"/teacher/writing/aufgabe-1?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/writing/aufgabe-1?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/writing/aufgabe-1?{query}", status_code=303)


@app.post("/teacher/speaking/aufgabe-{number}/create")
async def create_speaking_aufgabe(request: Request, number: int) -> RedirectResponse:
    if number not in TASK_PROFILES:
        query = urlencode({"error": "口语题号必须在 1-7 之间。"})
        return RedirectResponse(url=f"/teacher/speaking/aufgabe-{number}?{query}", status_code=303)

    form = await request.form()
    question_id = question_bank.new_question_id()
    question_dir = question_bank.get_question_dir("speaking", f"aufgabe_{number}", question_id)
    try:
        uploads = _form_uploads(form, "reference_images")
        reference_image_files, reference_image_paths = _save_reference_images(question_dir, uploads)
        params = {
            "api_key": str(form.get("api_key", "")),
            "topic": str(form.get("topic", "")).strip(),
            "reference_material": str(form.get("reference_material", "")).strip(),
            "reference_urls": str(form.get("reference_urls", "")).strip(),
            "image_notes": str(form.get("image_notes", "")).strip(),
            "difficulty": str(form.get("difficulty", "standard")),
            "examiner_role": str(form.get("examiner_role", "")).strip() or _default_speaking_role(number),
            "voice": str(form.get("voice", "Cherry")),
            "chart_count": int(form.get("chart_count", "1")),
            "chart_types": _parse_chart_types(form, int(form.get("chart_count", "1"))),
        }
        if not params["topic"]:
            raise RuntimeError("请填写参考主题。")
        job_id = job_manager.create(f"口语 Aufgabe {number}")

        def run_job() -> str:
            key = _resolve_api_key(params["api_key"])
            job_manager.update(job_id, step="整理参考素材")
            reference_bundle = _build_reference_material(params["reference_material"], params["reference_urls"])
            job_manager.update(job_id, step="调用文本模型生成口语题")
            generation = speaking_task_generator.generate(
                key,
                SpeakingTaskInput(
                    number=number,
                    topic=params["topic"],
                    reference_material=reference_bundle.combined_text,
                    image_notes=params["image_notes"],
                    difficulty=params["difficulty"],
                    examiner_role=params["examiner_role"],
                    voice=params["voice"],
                    chart_count=params["chart_count"],
                    chart_types=params["chart_types"],
                    reference_image_paths=reference_image_paths,
                ),
            )
            chart_files = []
            if generation.get("chart_specs"):
                job_manager.update(job_id, step="渲染 SVG 图表")
                chart_files = chart_renderer.render_charts(generation["chart_specs"], question_dir)
            job_manager.update(job_id, step="生成引子语音")
            audio_path = question_dir / "intro.wav"
            tts_service.synthesize_german(
                api_key=key,
                text=generation["examiner_intro"],
                voice=params["voice"],
                save_path=audio_path,
            )
            generation["audio"] = "intro.wav"
            generation["chart_files"] = chart_files
            generation["reference_image_count"] = len(reference_image_paths)
            job_manager.update(job_id, step="保存到本地题库")
            manifest = question_bank.save_speaking_aufgabe(
                question_id=question_id,
                number=number,
                topic_input=params["topic"],
                reference_material=reference_bundle.combined_text,
                difficulty=params["difficulty"],
                generation=generation,
                chart_files=chart_files,
                reference_image_files=reference_image_files,
                reference_sources=reference_bundle.sources,
            )
            return f"/teacher/speaking/aufgabe-{number}?created={manifest.id}"

        job_manager.start(job_id, run_job)
        return RedirectResponse(url=f"/teacher/speaking/aufgabe-{number}?job={job_id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/speaking/aufgabe-{number}?{query}", status_code=303)


@app.post("/teacher/speaking/test-set/create")
async def create_speaking_test_set(request: Request) -> RedirectResponse:
    question_id = question_bank.new_question_id()
    question_dir = question_bank.get_question_dir("speaking", "test_set", question_id)
    try:
        form = await request.form()
        key = _resolve_api_key(str(form.get("api_key", "")))
        difficulty = str(form.get("difficulty", "standard"))
        tasks = []
        reference_texts = []

        for number in range(1, 8):
            task_dir = question_dir / f"task_{number}"
            topic = str(form.get(f"task_{number}_topic", "")).strip()
            reference_material = str(form.get(f"task_{number}_reference_material", "")).strip()
            reference_urls = str(form.get(f"task_{number}_reference_urls", "")).strip()
            image_notes = str(form.get(f"task_{number}_image_notes", "")).strip()
            examiner_role = str(form.get(f"task_{number}_examiner_role", "")).strip()
            voice = str(form.get(f"task_{number}_voice", "Cherry"))
            chart_count = int(form.get(f"task_{number}_chart_count", "1"))
            chart_types = _parse_chart_types(form, chart_count, prefix=f"task_{number}_")
            if not topic:
                raise RuntimeError(f"请填写 Aufgabe {number} 的主题。")
            if not examiner_role:
                examiner_role = _default_speaking_role(number)

            reference_bundle = _build_reference_material(reference_material, reference_urls)
            reference_texts.append(reference_bundle.combined_text)
            uploads = _form_uploads(form, f"task_{number}_reference_images")
            _, reference_image_paths = _save_reference_images(task_dir, uploads)
            generated = speaking_task_generator.generate(
                key,
                SpeakingTaskInput(
                    number=number,
                    topic=topic,
                    reference_material=reference_bundle.combined_text,
                    image_notes=image_notes,
                    difficulty=difficulty,
                    examiner_role=examiner_role,
                    voice=voice,
                    chart_count=chart_count,
                    chart_types=chart_types,
                    reference_image_paths=reference_image_paths,
                ),
            )

            chart_files = []
            if generated.get("chart_specs"):
                chart_files = [
                    f"task_{number}/{filename}"
                    for filename in chart_renderer.render_charts(generated["chart_specs"], task_dir)
                ]

            audio_path = task_dir / "intro.wav"
            tts_service.synthesize_german(
                api_key=key,
                text=generated["examiner_intro"],
                voice=voice,
                save_path=audio_path,
            )
            generated["audio"] = f"task_{number}/intro.wav"
            generated["chart_files"] = chart_files
            generated["reference_image_count"] = len(reference_image_paths)
            tasks.append(generated)

        title = "Mündlicher Ausdruck Test-Set"
        topic_summary = " / ".join(task["title"] for task in tasks[:3])
        manifest = question_bank.save_speaking_test_set(
            question_id=question_id,
            title=title,
            topic_summary=topic_summary,
            tasks=tasks,
            reference_material="\n\n".join(reference_texts),
            reference_sources={"note": "Referenzquellen werden pro Aufgabe im kombinierten Material berücksichtigt."},
        )
        return RedirectResponse(url=f"/teacher/speaking/test-set?created={manifest.id}", status_code=303)
    except Exception as exc:
        query = urlencode({"error": str(exc)})
        return RedirectResponse(url=f"/teacher/speaking/test-set?{query}", status_code=303)


@app.get("/student", response_class=HTMLResponse)
def student_entry(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="student.html",
        context={
            "request": request,
            "student_url": "http://127.0.0.1:8001/",
        },
    )


def _build_voice_map(speaker_a_voice: str, speaker_b_voice: str) -> dict[str, str]:
    if speaker_a_voice != speaker_b_voice:
        return {"A": speaker_a_voice, "B": speaker_b_voice}

    fallback = "Ethan" if speaker_a_voice != "Ethan" else "Cherry"
    return {"A": speaker_a_voice, "B": fallback}


def _resolve_api_key(api_key: str) -> str:
    key = api_key.strip() or os.getenv("DASHSCOPE_API_KEY", "") or config_store.load_api_key()
    if not key:
        raise RuntimeError("请填写阿里云百炼 API Key，或设置环境变量 DASHSCOPE_API_KEY。")
    if api_key.strip():
        config_store.save_api_key(api_key.strip())
    return key


def _build_reference_material(reference_material: str, reference_urls: str) -> ReferenceMaterialBundle:
    return reference_material_service.build(reference_material, reference_urls)


def _save_reference_images(question_dir: Path, uploads: list[UploadFile]) -> tuple[list[str], list[Path]]:
    image_dir = question_dir / "reference_images"
    relative_files = []
    absolute_paths = []
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    valid_uploads = [upload for upload in uploads if upload and upload.filename]
    if not valid_uploads:
        return relative_files, absolute_paths

    image_dir.mkdir(parents=True, exist_ok=True)
    for index, upload in enumerate(valid_uploads[:6], start=1):
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in allowed_suffixes:
            raise RuntimeError("参考图片仅支持 PNG、JPG、JPEG 或 WEBP 格式。")
        filename = f"reference_{index}{suffix}"
        target = image_dir / filename
        with target.open("wb") as file:
            shutil.copyfileobj(upload.file, file)
        relative_files.append(f"reference_images/{filename}")
        absolute_paths.append(target)
    return relative_files, absolute_paths


def _form_uploads(form: object, field_name: str) -> list[UploadFile]:
    values = form.getlist(field_name) if hasattr(form, "getlist") else []
    return [value for value in values if isinstance(value, UploadFile) and value.filename]


def _parse_chart_types(form, count: int, prefix: str = "") -> list[str]:
    """Parse chart types from form fields for speaking tasks."""
    chart_types = []
    for i in range(1, count + 1):
        value = form.get(f"{prefix}chart_type_{i}")
        if value:
            chart_types.append(str(value))
    return chart_types

def _default_speaking_role(number: int) -> str:
    return {
        1: "Frau Reckmann vom Hochschulsport",
        2: "Christian, Studienkollege",
        3: "Frau Schöller, Deutschlehrerin",
        4: "Herr Dr. Rottmeier, Diskussionsleiter",
        5: "Mika, Studienfreund",
        6: "Herr Dr. Flügel, Seminarleiter",
        7: "Karla, Studienfreundin",
    }.get(number, "Gesprächspartner/in")
