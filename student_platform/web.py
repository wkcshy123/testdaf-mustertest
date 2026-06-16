"""FastAPI entry for the student practice system."""

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shared.question_bank import QuestionBankReader
from student_platform.config import QUESTION_BANK_DIR, STUDENT_ATTEMPTS_DIR
from student_platform.services.attempt_store import AttemptStore
from student_platform.services.question_presenter import QuestionPresenter, _time_limit_for

PACKAGE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TestDaF 学生答题系统", version="0.2.0")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
app.mount("/question-bank", StaticFiles(directory=QUESTION_BANK_DIR), name="question_bank")

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
question_reader = QuestionBankReader(QUESTION_BANK_DIR)
attempt_store = AttemptStore(STUDENT_ATTEMPTS_DIR)
presenter = QuestionPresenter(question_reader)

# Sections supported for online answering.
SUPPORTED_SECTIONS = {"listening", "reading", "writing"}


@app.on_event("startup")
def startup() -> None:
    STUDENT_ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "system": "student"}


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
        context={
            "request": request,
            "grouped": grouped,
            "total_count": len(all_questions),
        },
    )


@app.get("/practice/{section}/{task_type}/{question_id}", response_class=HTMLResponse)
def practice_question(
    request: Request, section: str, task_type: str, question_id: str
) -> HTMLResponse:
    question = question_reader.find_by_id(question_id)
    if not question:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_found.html",
            context={"request": request, "question_id": question_id},
            status_code=404,
        )

    view = presenter.present(question)
    if view is None:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_supported.html",
            context={"request": request, "question": question},
        )

    return templates.TemplateResponse(
        request=request,
        name="practice_question.html",
        context={
            "request": request,
            "view": view,
        },
    )


@app.post("/practice/{section}/{task_type}/{question_id}/submit")
def submit_attempt(
    request: Request,
    section: str,
    task_type: str,
    question_id: str,
    elapsed_seconds: int = Form(0),
    timed_out: bool = Form(False),
    answers_json: str = Form(""),
) -> RedirectResponse:
    import json

    question = question_reader.find_by_id(question_id)
    if not question:
        return RedirectResponse(url="/", status_code=303)

    try:
        answers = json.loads(answers_json) if answers_json else {}
    except json.JSONDecodeError:
        answers = {}

    params = question.get("parameters", {})
    answer_mode = params.get("answer_mode", "")
    time_limit = _time_limit_for(section, task_type)

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
    )
    return RedirectResponse(url=f"/attempt/{attempt_id}", status_code=303)


@app.get("/attempt/{attempt_id}", response_class=HTMLResponse)
def view_attempt(request: Request, attempt_id: str) -> HTMLResponse:
    data = attempt_store.load_attempt(attempt_id)
    if not data:
        return templates.TemplateResponse(
            request=request,
            name="practice_not_found.html",
            context={"request": request, "question_id": attempt_id},
            status_code=404,
        )
    return templates.TemplateResponse(
        request=request,
        name="attempt_result.html",
        context={
            "request": request,
            "meta": data["meta"],
            "answers": data["answers"],
        },
    )


@app.get("/attempts", response_class=HTMLResponse)
def attempts(request: Request) -> HTMLResponse:
    all_attempts = attempt_store.list_attempts()
    return templates.TemplateResponse(
        request=request,
        name="attempts.html",
        context={
            "request": request,
            "attempt_count": len(all_attempts),
            "attempts": all_attempts,
        },
    )
