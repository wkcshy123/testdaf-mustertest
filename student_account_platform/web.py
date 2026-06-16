"""FastAPI entry for the student account system (port 8002).

Responsibilities: self-service registration, login, logout, profile and
a public student list. It writes the shared ``students/`` directory,
which the answering system (8001) reads to resolve session cookies.
"""

from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from student_account_platform.config import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    STUDENT_SYSTEM_URL,
    STUDENTS_DIR,
)
from student_account_platform.services.account_store import AccountStore
from student_account_platform.services.session_store import SessionStore

PACKAGE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TestDaF 学生账号系统", version="0.1.0")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
account_store = AccountStore(STUDENTS_DIR)
session_store = SessionStore(STUDENTS_DIR, SESSION_TTL_SECONDS)


@app.on_event("startup")
def startup() -> None:
    STUDENTS_DIR.mkdir(parents=True, exist_ok=True)
    (STUDENTS_DIR / "sessions").mkdir(parents=True, exist_ok=True)


# ======================================================================
# Auth dependency
# ======================================================================
def current_student(request: Request) -> dict | None:
    """Resolve the logged-in account from the session cookie, or None."""
    token = request.cookies.get(SESSION_COOKIE)
    student_id = session_store.resolve(token)
    if not student_id:
        return None
    return account_store.find_by_id(student_id)


def require_student(request: Request) -> dict:
    """Like :func:`current_student` but raises a redirect to login when absent."""
    student = current_student(request)
    if not student:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return student


# ======================================================================
# Pages
# ======================================================================
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "system": "account"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    student = current_student(request)
    return templates.TemplateResponse(
        request=request,
        name="account_index.html",
        context={"request": request, "student": student},
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, error: str = "") -> HTMLResponse:
    if current_student(request):
        return RedirectResponse(url="/profile", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"request": request, "error": error},
    )


@app.post("/register")
def register_submit(
    username: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    try:
        student_id = account_store.register(
            username=username, password=password, name=name
        )
    except ValueError as exc:
        from urllib.parse import urlencode

        return RedirectResponse(
            url=f"/register?{urlencode({'error': str(exc)})}", status_code=303
        )
    token = session_store.create(student_id)
    resp = RedirectResponse(url="/profile", status_code=303)
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return resp


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = "") -> HTMLResponse:
    if current_student(request):
        return RedirectResponse(url="/profile", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "error": error},
    )


@app.post("/login")
def login_submit(
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    from urllib.parse import urlencode

    record = account_store.verify(username, password)
    if not record:
        return RedirectResponse(
            url=f"/login?{urlencode({'error': '用户名或密码错误。'})}", status_code=303
        )
    token = session_store.create(record["student_id"])
    resp = RedirectResponse(url="/profile", status_code=303)
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return resp


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    token = request.cookies.get(SESSION_COOKIE)
    session_store.destroy(token)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request) -> HTMLResponse:
    student = current_student(request)
    if not student:
        return RedirectResponse(url="/login", status_code=303)
    public = {k: v for k, v in student.items() if k != "password_hash"}
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "request": request,
            "student": public,
            "student_system_url": STUDENT_SYSTEM_URL,
        },
    )


@app.get("/students", response_class=HTMLResponse)
def students_list(request: Request) -> HTMLResponse:
    accounts = account_store.list_accounts()
    return templates.TemplateResponse(
        request=request,
        name="students_list.html",
        context={
            "request": request,
            "accounts": accounts,
            "account_count": len(accounts),
            "current": current_student(request),
        },
    )
