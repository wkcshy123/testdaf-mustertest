"""FastAPI entry for the student practice system."""

from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shared.question_bank import QuestionBankReader
from student_platform.config import (
    ACCOUNT_SYSTEM_URL,
    QUESTION_BANK_DIR,
    SCORING_SYSTEM_URL,
    SESSION_COOKIE,
    STUDENT_ATTEMPTS_DIR,
    STUDENTS_DIR,
)
from student_platform.services.attempt_store import AttemptStore
from student_platform.services.exam_builder import ExamBuilder, MODULE_ORDER
from student_platform.services.exam_store import ExamStore, MODULE_LABELS, MODULE_TIME_LIMITS
from student_platform.services.question_presenter import QuestionPresenter, _time_limit_for
from student_platform.services.student_store import StudentIdentityService

PACKAGE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TestDaF 学生答题系统", version="0.2.0")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
app.mount("/question-bank", StaticFiles(directory=QUESTION_BANK_DIR), name="question_bank")

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
question_reader = QuestionBankReader(QUESTION_BANK_DIR)
attempt_store = AttemptStore(STUDENT_ATTEMPTS_DIR)
exam_store = ExamStore(STUDENT_ATTEMPTS_DIR)
exam_builder = ExamBuilder(question_reader)
presenter = QuestionPresenter(question_reader)
identity_service = StudentIdentityService(STUDENTS_DIR)

# Sections supported for online answering.
SUPPORTED_SECTIONS = {"listening", "reading", "writing", "speaking"}


def current_student(request: Request) -> dict | None:
    """Resolve the logged-in student from the session cookie, or None.

    Used by the nav bar and browsing pages so anonymous visitors can still
    look around. Answering and submission routes use :func:`require_student`
    instead, which enforces a login.
    """
    token = request.cookies.get(SESSION_COOKIE)
    return identity_service.resolve(token)


def login_redirect() -> RedirectResponse:
    """Redirect an anonymous visitor to the account system's login page."""
    return RedirectResponse(url=f"{ACCOUNT_SYSTEM_URL}login", status_code=303)


def base_context(request: Request, **extra) -> dict:
    """Build a template context pre-seeded with the shared student nav state."""
    ctx = {
        "request": request,
        "current_student": current_student(request),
        "account_system_url": ACCOUNT_SYSTEM_URL,
        "scoring_system_url": SCORING_SYSTEM_URL,
    }
    ctx.update(extra)
    return ctx


@app.on_event("startup")
def startup() -> None:
    STUDENT_ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "system": "student"}


@app.get("/record-test", response_class=HTMLResponse)
def record_test(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="record_test.html",
        context=base_context(request),
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    all_questions = question_reader.list_questions()
    sections: dict[str, list[dict]] = {}
    for question in all_questions:
        section = question.get("section", "other")
        sections.setdefault(section, []).append(question)

    grouped = []
    for section_name, label in [
        ("listening", "听力 Hörverstehen"),
        ("reading", "阅读 Leseverstehen"),
        ("writing", "写作 Schriftlicher Ausdruck"),
        ("speaking", "口语 Mündlicher Ausdruck"),
    ]:
        items = sections.get(section_name, [])
        grouped.append(
            {
                "section": section_name,
                "label": label,
                "supported": section_name in SUPPORTED_SECTIONS,
                "count": len(items),
                "questions": items,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="student_index.html",
        context=base_context(
            request,
            grouped=grouped,
            total_count=len(all_questions),
        ),
    )


@app.get("/practice/{section}/{task_type}/{question_id}", response_class=HTMLResponse)
def practice_question(
    request: Request, section: str, task_type: str, question_id: str
) -> HTMLResponse:
    student = current_student(request)
    if not student:
        return login_redirect()

    question = question_reader.find_by_id(question_id)
    if not question:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_found.html",
            context=base_context(request, question_id=question_id),
            status_code=404,
        )

    view = presenter.present(question)
    if view is None:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_supported.html",
            context=base_context(request, question=question),
        )

    return templates.TemplateResponse(
        request=request,
        name="practice_question.html",
        context=base_context(request, view=view),
    )


@app.post("/practice/{section}/{task_type}/{question_id}/submit")
async def submit_attempt(
    request: Request,
    section: str,
    task_type: str,
    question_id: str,
    elapsed_seconds: int = Form(0),
    timed_out: bool = Form(False),
    answers_json: str = Form(""),
    audio_file: UploadFile | None = File(default=None),
) -> RedirectResponse:
    import json

    student = current_student(request)
    if not student:
        return login_redirect()

    question = question_reader.find_by_id(question_id)
    if not question:
        return RedirectResponse(url="/", status_code=303)

    try:
        answers = json.loads(answers_json) if answers_json else {}
    except json.JSONDecodeError:
        answers = {}

    writing_mode = answers.pop("_writing_mode", "")

    params = question.get("parameters", {})
    answer_mode = params.get("answer_mode", "")
    time_limit = _time_limit_for(section, task_type)

    audio_bytes = None
    audio_filename = "response.webm"
    if audio_file and audio_file.filename:
        audio_bytes = await audio_file.read()
        audio_filename = audio_file.filename

    attempt_id = attempt_store.save(
        question_id=question_id,
        section=section,
        task_type=task_type,
        answer_mode=answer_mode,
        title=question.get("title", ""),
        answers=answers,
        time_limit_seconds=time_limit,
        elapsed_seconds=elapsed_seconds,
        timed_out=timed_out,
        audio_bytes=audio_bytes,
        audio_filename=audio_filename,
        student_id=student["student_id"],
        student_name=student.get("name", ""),
        writing_mode=writing_mode,
    )
    return RedirectResponse(url=f"/attempt/{attempt_id}", status_code=303)


@app.post("/practice/{section}/{task_type}/{question_id}/refresh-submit")
async def submit_practice_refresh_attempt(
    request: Request,
    section: str,
    task_type: str,
    question_id: str,
    stage: str = Form(""),
) -> JSONResponse:
    """Submit a blank speaking practice answer after a started page refresh."""
    student = current_student(request)
    if not student:
        return JSONResponse({"ok": False, "error": "login_required"}, status_code=401)

    question = question_reader.find_by_id(question_id)
    if not question:
        return JSONResponse({"ok": False, "error": "question_not_found"}, status_code=404)

    params = question.get("parameters", {})
    answer_mode = params.get("answer_mode", "")
    if answer_mode != "spoken_response":
        return JSONResponse({"ok": False, "error": "not_speaking_question"}, status_code=400)

    attempt_id = attempt_store.save(
        question_id=question_id,
        section=section,
        task_type=task_type,
        answer_mode=answer_mode,
        title=question.get("title", ""),
        answers={
            "spoken": "",
            "status": "unanswered_due_to_refresh",
            "refreshed_stage": stage,
        },
        time_limit_seconds=_time_limit_for(section, task_type),
        elapsed_seconds=0,
        timed_out=False,
        student_id=student["student_id"],
        student_name=student.get("name", ""),
    )
    return JSONResponse({"ok": True, "redirect_url": f"/attempt/{attempt_id}"})


@app.get("/attempt/{attempt_id}", response_class=HTMLResponse)
def view_attempt(request: Request, attempt_id: str) -> HTMLResponse:
    data = attempt_store.load_attempt(attempt_id)
    if not data:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_found.html",
            context=base_context(request, question_id=attempt_id),
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request,
        name="attempt_result.html",
        context=base_context(
            request,
            meta=data["meta"],
            answers=data["answers"],
            attempt_id=attempt_id,
            has_audio=bool(data["meta"].get("audio_file")),
        ),
    )


@app.get("/attempt/{attempt_id}/audio")
def download_attempt_audio(attempt_id: str):
    from fastapi.responses import FileResponse

    data = attempt_store.load_attempt(attempt_id)
    if not data:
        return RedirectResponse(url="/", status_code=303)
    audio_filename = data["meta"].get("audio_file", "")
    if not audio_filename:
        return RedirectResponse(url=f"/attempt/{attempt_id}", status_code=303)
    audio_path = Path(data["attempt_dir"]) / audio_filename
    if not audio_path.exists():
        return RedirectResponse(url=f"/attempt/{attempt_id}", status_code=303)
    ext = audio_path.suffix.lower()
    mime_map = {"webm": "audio/webm", "ogg": "audio/ogg", "mp4": "audio/mp4", "wav": "audio/wav"}
    return FileResponse(
        path=str(audio_path),
        media_type=mime_map.get(ext, "application/octet-stream"),
        filename=audio_filename,
    )


@app.get("/attempts", response_class=HTMLResponse)
def attempts(request: Request) -> HTMLResponse:
    all_attempts = attempt_store.list_attempts()
    return templates.TemplateResponse(
        request=request,
        name="attempts.html",
        context=base_context(
            request,
            attempt_count=len(all_attempts),
            attempts=all_attempts,
        ),
    )


# ======================================================================
# Full exam mode (modular: reading → listening → writing → speaking)
# ======================================================================


@app.get("/exam", response_class=HTMLResponse)
def exam_start_page(request: Request) -> HTMLResponse:
    """Show exam assembly preview: pick one question per task type."""
    if not current_student(request):
        return login_redirect()
    result = exam_builder.build()
    return templates.TemplateResponse(
        request=request,
        name="exam_start.html",
        context=base_context(
            request,
            questions=result.questions,
            gaps=result.gaps,
            module_order=MODULE_ORDER,
            module_labels=MODULE_LABELS,
            module_time_limits=MODULE_TIME_LIMITS,
        ),
    )


@app.post("/exam/start")
def exam_start(request: Request) -> RedirectResponse:
    """Create an exam session and redirect to the first module."""
    if not current_student(request):
        return login_redirect()
    result = exam_builder.build()
    if result.gaps:
        from urllib.parse import urlencode

        query = urlencode({"error": "题库不足，无法组卷"})
        return RedirectResponse(url=f"/exam?{query}", status_code=303)

    exam_id = exam_store.create_exam(result.questions)
    first_module = MODULE_ORDER[0]
    return RedirectResponse(
        url=f"/exam/{exam_id}/{first_module}?question=0", status_code=303
    )


@app.get("/exam/{exam_id}/{module}", response_class=HTMLResponse)
def exam_module_page(
    request: Request, exam_id: str, module: str
) -> HTMLResponse:
    """Render one question within a module during the exam."""
    if not current_student(request):
        return login_redirect()
    exam = exam_store.load_exam(exam_id)
    if not exam:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_found.html",
            context=base_context(request, question_id=exam_id),
            status_code=404,
        )

    if module not in MODULE_ORDER:
        return RedirectResponse(url=f"/exam/{exam_id}/result", status_code=303)

    question_ids = exam.get("question_ids", {}).get(module, [])
    q_index = int(request.query_params.get("question", "0"))
    q_index = max(0, min(q_index, len(question_ids) - 1)) if question_ids else 0

    if not question_ids:
        return RedirectResponse(
            url=f"/exam/{exam_id}/{module}/submit", status_code=303
        )

    question_meta = question_reader.find_by_id(question_ids[q_index])
    view = presenter.present(question_meta) if question_meta else None

    module_index = MODULE_ORDER.index(module)
    titles = exam.get("question_titles", {}).get(module, [])

    return templates.TemplateResponse(
        request=request,
        name="exam_module.html",
        context=base_context(
            request,
            exam_id=exam_id,
            module=module,
            module_label=MODULE_LABELS.get(module, module),
            module_index=module_index,
            total_modules=len(MODULE_ORDER),
            module_time_limit=MODULE_TIME_LIMITS.get(module, 0),
            q_index=q_index,
            q_total=len(question_ids),
            question_ids=question_ids,
            question_titles=titles,
            view=view,
        ),
    )


@app.post("/exam/{exam_id}/speaking/refresh-submit")
async def exam_speaking_refresh_submit(
    request: Request,
    exam_id: str,
    q_index: int = Form(...),
    stage: str = Form(""),
    elapsed_seconds: int = Form(0),
) -> JSONResponse:
    """Submit a blank speaking answer when a started question is refreshed."""
    student = current_student(request)
    if not student:
        return JSONResponse({"ok": False, "error": "login_required"}, status_code=401)

    exam = exam_store.load_exam(exam_id)
    if not exam:
        return JSONResponse({"ok": False, "error": "exam_not_found"}, status_code=404)

    question_ids = exam.get("question_ids", {}).get("speaking", [])
    if q_index < 0 or q_index >= len(question_ids):
        return JSONResponse({"ok": False, "error": "question_not_found"}, status_code=404)

    qid = question_ids[q_index]
    question_meta = question_reader.find_by_id(qid)
    if not question_meta:
        return JSONResponse({"ok": False, "error": "question_not_found"}, status_code=404)

    params = question_meta.get("parameters", {})
    attempt_store.save(
        question_id=qid,
        section="speaking",
        task_type=question_meta.get("task_type", ""),
        answer_mode=params.get("answer_mode", ""),
        title=question_meta.get("title", ""),
        answers={
            "spoken": "",
            "status": "unanswered_due_to_refresh",
            "exam_q_index": q_index,
            "refreshed_stage": stage,
        },
        time_limit_seconds=MODULE_TIME_LIMITS.get("speaking", 0),
        elapsed_seconds=max(0, elapsed_seconds),
        timed_out=False,
        exam_id=exam_id,
        student_id=student["student_id"],
        student_name=student.get("name", ""),
    )

    next_url = (
        f"/exam/{exam_id}/speaking?question={q_index + 1}"
        if q_index + 1 < len(question_ids)
        else ""
    )
    return JSONResponse(
        {
            "ok": True,
            "next_url": next_url,
            "submit_module": q_index + 1 >= len(question_ids),
        }
    )


@app.post("/exam/{exam_id}/{module}/submit")
async def exam_module_submit(
    request: Request, exam_id: str, module: str
) -> RedirectResponse:
    """Submit all questions in the current module, advance to next."""
    import json as _json

    student = current_student(request)
    if not student:
        return login_redirect()

    exam = exam_store.load_exam(exam_id)
    if not exam:
        return RedirectResponse(url="/exam", status_code=303)

    form = await request.form()
    question_ids = exam.get("question_ids", {}).get(module, [])
    existing_exam_question_ids = {
        item.get("question_id")
        for item in attempt_store.list_attempts()
        if item.get("exam_id") == exam_id
    }

    for qid in question_ids:
        if qid in existing_exam_question_ids:
            continue
        question_meta = question_reader.find_by_id(qid)
        if not question_meta:
            continue
        raw = form.get(f"answers_{qid}", "")
        try:
            answers = _json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            answers = {}

        params = question_meta.get("parameters", {})
        attempt_store.save(
            question_id=qid,
            section=module,
            task_type=question_meta.get("task_type", ""),
            answer_mode=params.get("answer_mode", ""),
            title=question_meta.get("title", ""),
            answers=answers,
            time_limit_seconds=MODULE_TIME_LIMITS.get(module, 0),
            elapsed_seconds=int(form.get("elapsed_seconds", "0")),
            timed_out=form.get("timed_out") == "true",
            exam_id=exam_id,
            student_id=student["student_id"],
            student_name=student.get("name", ""),
        )

    module_index = MODULE_ORDER.index(module) if module in MODULE_ORDER else 0
    if module_index + 1 < len(MODULE_ORDER):
        next_module = MODULE_ORDER[module_index + 1]
        exam_store.update_exam(exam_id, current_module=next_module)
        return RedirectResponse(
            url=f"/exam/{exam_id}/{next_module}?question=0", status_code=303
        )

    exam_store.update_exam(exam_id, status="completed")
    return RedirectResponse(url=f"/exam/{exam_id}/result", status_code=303)


@app.get("/exam/{exam_id}/result", response_class=HTMLResponse)
def exam_result(request: Request, exam_id: str) -> HTMLResponse:
    """Show the full exam result summary."""
    exam = exam_store.load_exam(exam_id)
    if not exam:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_found.html",
            context=base_context(request, question_id=exam_id),
            status_code=404,
        )

    all_attempts = attempt_store.list_attempts()
    exam_attempts = [a for a in all_attempts if a.get("exam_id") == exam_id]

    return templates.TemplateResponse(
        request=request,
        name="exam_result.html",
        context=base_context(
            request,
            exam=exam,
            module_order=MODULE_ORDER,
            module_labels=MODULE_LABELS,
            attempts=exam_attempts,
        ),
    )


@app.get("/exams", response_class=HTMLResponse)
def exam_list(request: Request) -> HTMLResponse:
    """List all exam sessions."""
    exams = exam_store.list_exams()
    return templates.TemplateResponse(
        request=request,
        name="exam_list.html",
        context=base_context(
            request,
            exams=exams,
            exam_count=len(exams),
        ),
    )
