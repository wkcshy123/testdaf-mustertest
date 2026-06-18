from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import jinja2

from scoring_platform.config import (
    SECTION_LABELS, DIMENSION_LABELS, DIMENSION_DESCRIPTIONS,
)
from scoring_platform.services.auth import get_user, resolve_student, list_all_students
from scoring_platform.services.report_builder import (
    score_attempt, list_graded_attempts, build_exam_summary,
)
from scoring_platform.services.export_service import export_word_all_students, export_word_student
from scoring_platform.services.speaking_store import (
    speaking_for_render, save_speaking, list_all_speaking,
)
from student_account_platform.services.account_store import AccountStore
from student_account_platform.config import STUDENTS_DIR

from pypinyin import pinyin, Style

app = FastAPI(title="Scoring Platform")

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="score_static")

account_store = AccountStore(STUDENTS_DIR)


def _ctx(request: Request, **extra) -> dict:
    user = get_user(request)
    return {
        "request": request,
        "user": user,
        "section_labels": SECTION_LABELS,
        "dimension_labels": DIMENSION_LABELS,
        "dimension_descriptions": DIMENSION_DESCRIPTIONS,
        **extra,
    }


def _render(tpl: str, request: Request, **extra) -> HTMLResponse:
    ctx = _ctx(request, **extra)
    template = _jinja_env.get_template(tpl)
    return HTMLResponse(template.render(ctx))


def _is_teacher(user: dict | None) -> bool:
    return bool(user and user.get("role") == "teacher")


def _redirect_if_not_logged_in(user: dict | None) -> RedirectResponse | None:
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return None


def _redirect_if_not_teacher(user: dict | None) -> RedirectResponse | None:
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _is_teacher(user):
        return RedirectResponse(url="/student", status_code=303)
    return None


def _can_view_attempt(user: dict, result: dict) -> bool:
    return _is_teacher(user) or result.get("student_id") == user.get("student_id")


def _can_view_exam(user: dict, exam: dict) -> bool:
    return _is_teacher(user) or exam.get("student_id") == user.get("student_id")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_user(request)
    if not user:
        return _render("login.html", request, error="")
    if user.get("role") == "teacher":
        return RedirectResponse(url="/teacher", status_code=303)
    return RedirectResponse(url="/student", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    user = get_user(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    return _render("login.html", request, error=error)


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    record = account_store.verify(username, password)
    if not record:
        return RedirectResponse(url="/login?error=%E7%94%A8%E6%88%B7%E5%90%8D%E6%88%96%E5%AF%86%E7%A0%81%E9%94%99%E8%AF%AF%E3%80%82", status_code=303)
    from student_account_platform.services.session_store import SessionStore
    from student_account_platform.config import SESSION_TTL_SECONDS, SESSION_COOKIE
    session_store = SessionStore(STUDENTS_DIR, SESSION_TTL_SECONDS)
    token = session_store.create(record["student_id"])
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key=SESSION_COOKIE, value=token, httponly=True, samesite="lax", max_age=SESSION_TTL_SECONDS)
    return resp


@app.get("/logout")
def logout(request: Request):
    from student_account_platform.services.session_store import SessionStore
    from student_account_platform.config import SESSION_TTL_SECONDS, SESSION_COOKIE
    session_store = SessionStore(STUDENTS_DIR, SESSION_TTL_SECONDS)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session_store.destroy(token)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/student", response_class=HTMLResponse)
def student_home(request: Request):
    user = get_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    sid = user["student_id"]

    results = [r for r in list_graded_attempts(sid) if r["section"] != "speaking"]

    latest_practice = {}
    for r in results:
        sec = r["section"]
        if sec not in ("reading", "listening", "writing"):
            continue
        if sec not in latest_practice:
            latest_practice[sec] = r

    latest_exam = None
    seen_exams = set()
    for r in results:
        eid = r.get("exam_id", "")
        if eid and eid not in seen_exams:
            seen_exams.add(eid)
            exam = build_exam_summary(eid)
            if exam and not latest_exam:
                latest_exam = exam
                break

    return _render("student_home.html", request, latest_exam=latest_exam, latest_practice=latest_practice)


@app.get("/student/list", response_class=HTMLResponse)
def student_list(request: Request):
    user = get_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    sid = user["student_id"]
    sort = request.query_params.get("sort", "time")
    results = [r for r in list_graded_attempts(sid) if r["section"] != "speaking"]
    if sort == "section":
        results = sorted(results, key=lambda r: (r["section"], r["submitted_at"]), reverse=True)
    return _render("student_list.html", request, results=results, sort=sort)


@app.get("/score/{attempt_id}", response_class=HTMLResponse)
def score_detail(request: Request, attempt_id: str):
    user = get_user(request)
    if redirect := _redirect_if_not_logged_in(user):
        return redirect
    result = score_attempt(attempt_id)
    if not result:
        return _render("student_home.html", request)
    if not _can_view_attempt(user, result):
        return RedirectResponse(url="/student", status_code=303)
    return _render("score_objective.html", request, result=result)


@app.get("/score/exam/{exam_id}", response_class=HTMLResponse)
def score_exam(request: Request, exam_id: str):
    user = get_user(request)
    if redirect := _redirect_if_not_logged_in(user):
        return redirect
    exam = build_exam_summary(exam_id)
    if not exam:
        return _render("student_home.html", request)
    if not _can_view_exam(user, exam):
        return RedirectResponse(url="/student", status_code=303)
    return _render("score_exam.html", request, exam=exam)


def _latest_time(sid: str) -> str:
    for r in list_graded_attempts(sid):
        return r.get("submitted_at", "")
    return ""


@app.get("/teacher", response_class=HTMLResponse)
def teacher_home(request: Request):
    user = get_user(request)
    if redirect := _redirect_if_not_teacher(user):
        return redirect

    sort = request.query_params.get("sort", "name")
    all_students = [s for s in list_all_students() if s.get("role") != "teacher"]

    if sort == "name":
        all_students.sort(key=lambda s: "".join(p[0] for p in pinyin(s["name"], style=Style.TONE3)))
    elif sort == "time":
        all_students.sort(key=lambda s: _latest_time(s["student_id"]) or "", reverse=True)

    all_results = list_graded_attempts()
    all_speaking = list_all_speaking()
    student_rows = {}
    for s in all_students:
        sid = s["student_id"]
        spk = all_speaking.get(sid, {})
        row = {
            "reading_tdn": 0, "reading_label": "—",
            "listening_tdn": 0, "listening_label": "—",
            "writing_tdn": 0, "writing_label": "—",
            "speaking_tdn": spk.get("overall_tdn", 0) if spk.get("overall_label") else 0,
            "speaking_label": spk.get("overall_label") or "—",
            "last_exam": "—",
        }
        for r in all_results:
            if r["student_id"] != sid:
                continue
            sec = r["section"]
            if sec == "reading" and row["reading_tdn"] == 0:
                row["reading_tdn"] = r["tdn"]
                row["reading_label"] = r["tdn_label"]
            if sec == "listening" and row["listening_tdn"] == 0:
                row["listening_tdn"] = r["tdn"]
                row["listening_label"] = r["tdn_label"]
            if sec == "writing" and row["writing_tdn"] == 0:
                row["writing_tdn"] = r["tdn"]
                row["writing_label"] = r["tdn_label"]
            if r["exam_id"]:
                row["last_exam"] = r["submitted_at"][:10]
        student_rows[sid] = row

    return _render("teacher_home.html", request, students=all_students, student_rows=student_rows, sort=sort)


def _find_speaking_attempt_audio_for_student(student_id: str) -> list[dict]:
    from scoring_platform.config import STUDENT_ATTEMPTS_DIR
    from shared.file_io.atomic_json import read_json

    attempts: list[dict] = []
    if not STUDENT_ATTEMPTS_DIR.exists():
        return attempts

    for attempt_dir in sorted(STUDENT_ATTEMPTS_DIR.glob("attempt_*")):
        meta_path = attempt_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = read_json(meta_path)
        except Exception:
            continue
        if meta.get("section") != "speaking" or meta.get("student_id") != student_id:
            continue
        audio_file = meta.get("audio_file", "")
        if not audio_file or not (attempt_dir / audio_file).exists():
            continue
        attempts.append({
            "attempt_id": attempt_dir.name,
            "task_type": meta.get("task_type", ""),
            "audio_file": audio_file,
            "title": meta.get("title", ""),
            "submitted_at": meta.get("submitted_at", ""),
        })

    def _task_order(a: dict) -> int:
        tt = a.get("task_type", "")
        try:
            return int(tt.replace("aufgabe_", ""))
        except (ValueError, AttributeError):
            return 99

    attempts.sort(key=_task_order)
    return attempts


@app.get("/speaking-audio/{attempt_id}")
def speaking_audio(attempt_id: str):
    from fastapi.responses import FileResponse
    from shared.file_io.atomic_json import read_json

    attempt_dir = STUDENT_ATTEMPTS_DIR / attempt_id
    if not attempt_dir.exists():
        return RedirectResponse(url="/", status_code=303)
    meta = read_json(attempt_dir / "meta.json")
    audio_file = (meta or {}).get("audio_file", "")
    if not audio_file:
        return RedirectResponse(url="/", status_code=303)
    audio_path = attempt_dir / audio_file
    if not audio_path.exists():
        return RedirectResponse(url="/", status_code=303)
    ext = audio_path.suffix.lower()
    mime_map = {"webm": "audio/webm", "ogg": "audio/ogg", "mp4": "audio/mp4", "wav": "audio/wav"}
    return FileResponse(
        path=str(audio_path),
        media_type=mime_map.get(ext, "application/octet-stream"),
        filename=audio_file,
    )


@app.get("/teacher/student/{student_id}", response_class=HTMLResponse)
def teacher_student_view(request: Request, student_id: str):
    user = get_user(request)
    if redirect := _redirect_if_not_teacher(user):
        return redirect

    results = list_graded_attempts(student_id)
    latest_practice = {}
    for r in results:
        sec = r["section"]
        if sec not in ("reading", "listening", "writing"):
            continue
        if sec not in latest_practice:
            latest_practice[sec] = r

    student_name = student_id
    for s in list_all_students():
        if s["student_id"] == student_id:
            student_name = s["name"]
            break

    seen_exams = set()
    latest_exam = None
    for r in results:
        eid = r.get("exam_id", "")
        if eid and eid not in seen_exams:
            seen_exams.add(eid)
            exam = build_exam_summary(eid)
            if exam and not latest_exam:
                latest_exam = exam
                break

    speaking_audio_attempts = _find_speaking_attempt_audio_for_student(student_id)

    return _render("student_home.html", request, latest_exam=latest_exam, latest_practice=latest_practice, override_name=student_name, override_name_id=student_id, speaking=speaking_for_render(student_id), speaking_audio_attempts=speaking_audio_attempts, is_teacher_view=True, sort=request.query_params.get("sort", "name"))


@app.post("/teacher/student/{student_id}/speaking")
def save_student_speaking(
    request: Request,
    student_id: str,
    overall_tdn: str = Form(""),
    a1: str = Form(""), a2: str = Form(""), a3: str = Form(""),
    a4: str = Form(""), a5: str = Form(""), a6: str = Form(""), a7: str = Form(""),
):
    user = get_user(request)
    if redirect := _redirect_if_not_teacher(user):
        return redirect

    student_name = student_id
    for s in list_all_students():
        if s["student_id"] == student_id:
            student_name = s["name"]
            break

    task_scores = {"aufgabe_1": a1, "aufgabe_2": a2, "aufgabe_3": a3,
                   "aufgabe_4": a4, "aufgabe_5": a5, "aufgabe_6": a6,
                   "aufgabe_7": a7}
    task_scores = {k: v for k, v in task_scores.items() if v}

    save_speaking(student_id, student_name, overall_tdn, task_scores)

    sort = request.query_params.get("sort", "name")
    return RedirectResponse(url=f"/teacher/student/{student_id}?sort={sort}", status_code=303)


@app.get("/teacher/export/word")
def teacher_export_word(request: Request):
    user = get_user(request)
    if redirect := _redirect_if_not_teacher(user):
        return redirect
    sort = request.query_params.get("sort", "name")
    data = export_word_all_students(sort=sort)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=TestDaF_Grades.docx"},
    )


@app.get("/teacher/export/word/{student_id}")
def teacher_export_student_word(request: Request, student_id: str):
    user = get_user(request)
    if redirect := _redirect_if_not_teacher(user):
        return redirect
    data = export_word_student(student_id)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={student_id}_grades.docx"},
    )
