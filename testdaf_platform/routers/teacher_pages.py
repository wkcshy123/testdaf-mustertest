"""Teacher 出题页面 GET 路由（表单页 + 预览页）。"""

import markdown
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from testdaf_platform.storage.question_bank import QuestionBank


def create_router(
    *,
    templates: Jinja2Templates,
    question_bank: QuestionBank,
    voices: dict,
    task_profiles: dict,
) -> APIRouter:
    router = APIRouter()

    def _list_listening_questions(task_type: str) -> list[dict]:
        return _list_questions("listening", task_type)

    def _list_questions(section: str, task_type: str) -> list[dict]:
        questions = question_bank.list_questions(section=section)
        return [question for question in questions if question.get("task_type") == task_type]

    def _load_preview(questions: list[dict], created: str | None) -> dict | None:
        if not created:
            return None

        question = next((item for item in questions if item.get("id") == created), None)
        if not question:
            return None

        bundle = question_bank.load_question_bundle(question["_path"])
        preview_markdown = bundle.get("preview", "")
        return {
            "manifest": bundle["manifest"],
            "path": bundle["path"],
            "html": markdown.markdown(
                preview_markdown,
                extensions=["extra", "sane_lists"],
                output_format="html5",
            ),
        }

    # ------------------------------------------------------------------
    # 老师首页
    # ------------------------------------------------------------------

    @router.get("/teacher", response_class=HTMLResponse)
    def teacher_dashboard(request: Request) -> HTMLResponse:
        questions = question_bank.list_questions()
        listening_questions = [item for item in questions if item.get("section") == "listening"]
        reading_questions = [item for item in questions if item.get("section") == "reading"]
        writing_questions = [item for item in questions if item.get("section") == "writing"]
        speaking_questions = [item for item in questions if item.get("section") == "speaking"]
        return templates.TemplateResponse(
            request=request,
            name="teacher.html",
            context={
                "request": request,
                "questions": questions,
                "listening_count": len(listening_questions),
                "reading_count": len(reading_questions),
                "writing_count": len(writing_questions),
                "speaking_count": len(speaking_questions),
                "speaking_profiles": task_profiles,
                "error": request.query_params.get("error"),
            },
        )

    # ------------------------------------------------------------------
    # 听力出题页面
    # ------------------------------------------------------------------

    @router.get("/teacher/listening/aufgabe-1", response_class=HTMLResponse)
    def teacher_listening_aufgabe_1(request: Request) -> HTMLResponse:
        questions = _list_listening_questions("aufgabe_1")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_listening_aufgabe_1.html",
            context={
                "request": request,
                "questions": questions,
                "voices": voices,
                "created": created,
                "error": request.query_params.get("error"),
                "job_id": request.query_params.get("job"),
                "preview": preview,
            },
        )

    @router.get("/teacher/listening/aufgabe-2", response_class=HTMLResponse)
    def teacher_listening_aufgabe_2(request: Request) -> HTMLResponse:
        questions = _list_listening_questions("aufgabe_2")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_listening_aufgabe_2.html",
            context={
                "request": request,
                "questions": questions,
                "voices": voices,
                "created": created,
                "error": request.query_params.get("error"),
                "job_id": request.query_params.get("job"),
                "preview": preview,
            },
        )

    @router.get("/teacher/listening/aufgabe-3", response_class=HTMLResponse)
    def teacher_listening_aufgabe_3(request: Request) -> HTMLResponse:
        questions = _list_listening_questions("aufgabe_3")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_listening_aufgabe_3.html",
            context={
                "request": request,
                "questions": questions,
                "voices": voices,
                "created": created,
                "error": request.query_params.get("error"),
                "job_id": request.query_params.get("job"),
                "preview": preview,
            },
        )

    # ------------------------------------------------------------------
    # 阅读出题页面
    # ------------------------------------------------------------------

    @router.get("/teacher/reading/aufgabe-1", response_class=HTMLResponse)
    def teacher_reading_aufgabe_1(request: Request) -> HTMLResponse:
        questions = _list_questions("reading", "aufgabe_1")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_reading_aufgabe_1.html",
            context={
                "request": request,
                "questions": questions,
                "created": created,
                "error": request.query_params.get("error"),
                "job_id": request.query_params.get("job"),
                "preview": preview,
                "task_label": "阅读 Aufgabe 1",
                "task_url": "/teacher/reading/aufgabe-1",
            },
        )

    @router.get("/teacher/reading/aufgabe-2", response_class=HTMLResponse)
    def teacher_reading_aufgabe_2(request: Request) -> HTMLResponse:
        questions = _list_questions("reading", "aufgabe_2")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_reading_aufgabe_2.html",
            context={
                "request": request,
                "questions": questions,
                "created": created,
                "error": request.query_params.get("error"),
                "job_id": request.query_params.get("job"),
                "preview": preview,
                "task_label": "阅读 Aufgabe 2",
                "task_url": "/teacher/reading/aufgabe-2",
            },
        )

    @router.get("/teacher/reading/aufgabe-3", response_class=HTMLResponse)
    def teacher_reading_aufgabe_3(request: Request) -> HTMLResponse:
        questions = _list_questions("reading", "aufgabe_3")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_reading_aufgabe_3.html",
            context={
                "request": request,
                "questions": questions,
                "created": created,
                "error": request.query_params.get("error"),
                "job_id": request.query_params.get("job"),
                "preview": preview,
                "task_label": "阅读 Aufgabe 3",
                "task_url": "/teacher/reading/aufgabe-3",
            },
        )

    # ------------------------------------------------------------------
    # 写作出题页面
    # ------------------------------------------------------------------

    @router.get("/teacher/writing/aufgabe-1", response_class=HTMLResponse)
    def teacher_writing_aufgabe_1(request: Request) -> HTMLResponse:
        questions = _list_questions("writing", "aufgabe_1")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_writing_aufgabe_1.html",
            context={
                "request": request,
                "questions": questions,
                "created": created,
                "error": request.query_params.get("error"),
                "job_id": request.query_params.get("job"),
                "preview": preview,
                "task_label": "写作 Aufgabe 1",
                "task_url": "/teacher/writing/aufgabe-1",
            },
        )

    # ------------------------------------------------------------------
    # 口语出题页面（test-set 必须在 aufgabe-{number} 之前注册）
    # ------------------------------------------------------------------

    @router.get("/teacher/speaking/test-set", response_class=HTMLResponse)
    def teacher_speaking_test_set(request: Request) -> HTMLResponse:
        questions = _list_questions("speaking", "test_set")
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_speaking_test_set.html",
            context={
                "request": request,
                "questions": questions,
                "voices": voices,
                "task_profiles": task_profiles,
                "created": created,
                "error": request.query_params.get("error"),
                "preview": preview,
                "task_label": "口语 7 题套卷",
                "task_url": "/teacher/speaking/test-set",
            },
        )

    @router.get("/teacher/speaking/aufgabe-{number}", response_class=HTMLResponse)
    def teacher_speaking_aufgabe(request: Request, number: int) -> HTMLResponse:
        if number not in task_profiles:
            return templates.TemplateResponse(
                request=request,
                name="teacher_speaking_task.html",
                context={"request": request, "error": "口语题号必须在 1-7 之间。"},
                status_code=404,
            )
        task_type = f"aufgabe_{number}"
        questions = _list_questions("speaking", task_type)
        created = request.query_params.get("created")
        preview = _load_preview(questions, created)
        return templates.TemplateResponse(
            request=request,
            name="teacher_speaking_task.html",
            context={
                "request": request,
                "number": number,
                "profile": task_profiles[number],
                "questions": questions,
                "voices": voices,
                "created": created,
                "job_id": request.query_params.get("job"),
                "error": request.query_params.get("error"),
                "preview": preview,
                "task_label": f"口语 Aufgabe {number}",
                "task_url": f"/teacher/speaking/aufgabe-{number}",
            },
        )

    return router
