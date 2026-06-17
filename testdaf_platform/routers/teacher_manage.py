"""Teacher question-bank management routes."""

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from testdaf_platform.services.export_service import ExportService
from testdaf_platform.storage.question_bank import QuestionBank

SECTIONS = ("listening", "reading", "writing", "speaking")
SECTION_LABELS = {
    "listening": "听力 Hörverstehen",
    "reading": "阅读 Leseverstehen",
    "writing": "写作 Schriftlicher Ausdruck",
    "speaking": "口语 Mündlicher Ausdruck",
}


def create_router(
    *,
    templates: Jinja2Templates,
    question_bank: QuestionBank,
    export_service: ExportService,
) -> APIRouter:
    router = APIRouter()

    @router.get("/teacher/manage/trash", response_class=HTMLResponse)
    def teacher_trash(request: Request) -> HTMLResponse:
        trash_items = question_bank.list_trash()
        return templates.TemplateResponse(
            request=request,
            name="teacher_trash.html",
            context={
                "request": request,
                "trash_items": trash_items,
                "message": request.query_params.get("message"),
            },
        )

    @router.get("/teacher/manage/{section}", response_class=HTMLResponse)
    def teacher_manage_section(request: Request, section: str) -> HTMLResponse:
        if section not in SECTIONS:
            return RedirectResponse(url="/teacher", status_code=303)
        all_items = question_bank.list_questions(section=section)
        sort_by = request.query_params.get("sort", "created")
        order = request.query_params.get("order", "desc")
        if sort_by == "title":
            all_items.sort(key=lambda item: str(item.get("title", "")).lower(), reverse=(order == "desc"))
        elif sort_by == "task_type":
            all_items.sort(key=lambda item: str(item.get("task_type", "")), reverse=(order == "desc"))
        else:
            all_items.sort(key=lambda item: str(item.get("created_at", "")), reverse=(order != "asc"))
        return templates.TemplateResponse(
            request=request,
            name="teacher_manage.html",
            context={
                "request": request,
                "section": section,
                "section_label": SECTION_LABELS.get(section, section),
                "questions": all_items,
                "sort_by": sort_by,
                "order": order,
                "message": request.query_params.get("message"),
            },
        )

    @router.post("/teacher/manage/delete")
    async def delete_question(request: Request) -> RedirectResponse:
        form = await request.form()
        path = str(form.get("path", ""))
        section = str(form.get("section", "listening"))
        sort_by = str(form.get("sort_by", "created"))
        order = str(form.get("order", "desc"))
        try:
            question_bank.move_to_trash(path)
            query = urlencode({"sort": sort_by, "order": order, "message": "已移至垃圾箱"})
            return RedirectResponse(url=f"/teacher/manage/{section}?{query}", status_code=303)
        except Exception as exc:
            query = urlencode({"sort": sort_by, "order": order, "message": f"删除失败: {exc}"})
            return RedirectResponse(url=f"/teacher/manage/{section}?{query}", status_code=303)

    @router.post("/teacher/manage/restore")
    async def restore_question(request: Request) -> RedirectResponse:
        form = await request.form()
        trash_path = str(form.get("trash_path", ""))
        try:
            question_bank.restore_from_trash(trash_path)
            return RedirectResponse(url="/teacher/manage/trash?message=已恢复", status_code=303)
        except Exception as exc:
            query = urlencode({"message": f"恢复失败: {exc}"})
            return RedirectResponse(url=f"/teacher/manage/trash?{query}", status_code=303)

    @router.get("/teacher/manage/download/{fmt}")
    def download_question(request: Request, fmt: str) -> Response:
        path = request.query_params.get("path", "")
        if not path:
            return RedirectResponse(url="/teacher", status_code=303)
        if fmt not in ("docx",):
            return RedirectResponse(url="/teacher", status_code=303)
        try:
            file_path = export_service.export_questions_only(path)
            return FileResponse(
                path=str(file_path),
                filename=file_path.name,
                media_type="application/octet-stream",
            )
        except Exception as exc:
            query = urlencode({"error": f"导出失败: {exc}"})
            return RedirectResponse(url=f"/teacher?{query}", status_code=303)

    @router.post("/teacher/manage/rename")
    async def rename_question(request: Request) -> RedirectResponse:
        form = await request.form()
        path = str(form.get("path", ""))
        new_title = str(form.get("new_title", "")).strip()
        section = str(form.get("section", "listening"))
        sort_by = str(form.get("sort_by", "created"))
        order = str(form.get("order", "desc"))
        if not new_title:
            query = urlencode({"sort": sort_by, "order": order, "message": "标题不能为空"})
            return RedirectResponse(url=f"/teacher/manage/{section}?{query}", status_code=303)
        try:
            question_bank.rename_question(path, new_title)
            query = urlencode({"sort": sort_by, "order": order, "message": "已改名"})
            return RedirectResponse(url=f"/teacher/manage/{section}?{query}", status_code=303)
        except Exception as exc:
            query = urlencode({"sort": sort_by, "order": order, "message": f"改名失败: {exc}"})
            return RedirectResponse(url=f"/teacher/manage/{section}?{query}", status_code=303)

    return router
