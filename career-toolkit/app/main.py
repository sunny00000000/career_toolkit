"""
FastAPI entry point. Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
(see run.sh / README.md for the full deploy story)
"""
import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, gemini_client, history, job_search, prompts, resume_files, tracker
from .models import (
    InterviewRequest,
    JobMatchRequest,
    LoginRequest,
    ResumeRequest,
    TrackJobRequest,
    UpdateJobNotesRequest,
    UpdateJobStatusRequest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("career_toolkit")

for warning in config.startup_warnings():
    logger.warning(warning)

app = FastAPI(title="Career Toolkit")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))

# --- naive in-memory, per-IP, sliding-window rate limiter ---------------
# Good enough for a single-user tool on a single process. If you ever run
# multiple worker processes behind a load balancer, replace this with a
# shared store (e.g. Redis) since each worker would otherwise keep its own
# counters.
_requests: dict[str, deque] = defaultdict(deque)
_RATE_WINDOW_SECONDS = 60


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    q = _requests[ip]
    while q and now - q[0] > _RATE_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MINUTE:
        return True
    q.append(now)
    return False


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _require_api_auth(request: Request) -> None:
    if not auth.is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


# --- login attempt limiting -----------------------------------------------
# Separate from the limiter above: brute-forcing the one shared password is
# a different threat model, worth a stricter, longer window. Only failed
# attempts count, so a correct password never gets penalized.
_login_attempts: dict[str, deque] = defaultdict(deque)
_LOGIN_WINDOW_SECONDS = 600  # 10 minutes
_LOGIN_MAX_ATTEMPTS = 6


def _login_is_locked(ip: str) -> bool:
    now = time.time()
    q = _login_attempts[ip]
    while q and now - q[0] > _LOGIN_WINDOW_SECONDS:
        q.popleft()
    return len(q) >= _LOGIN_MAX_ATTEMPTS


def _record_failed_login(ip: str) -> None:
    _login_attempts[ip].append(time.time())


# --- auth routes ----------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if auth.is_authenticated(request):
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, payload: LoginRequest):
    ip = _client_ip(request)
    if _login_is_locked(ip):
        raise HTTPException(
            status_code=429, detail="Too many attempts -- wait a few minutes and try again."
        )
    if not auth.check_password(payload.password):
        _record_failed_login(ip)
        raise HTTPException(status_code=401, detail="Incorrect password")
    request.session["authenticated"] = True
    return {"ok": True}


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


# --- pages ------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    redirect = auth.require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        "index.html", {"request": request, "recent": history.list_recent(20)}
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/history/{entry_id}")
def get_history_entry(entry_id: int, request: Request):
    _require_api_auth(request)
    entry = history.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    return entry


# --- generation endpoints -----------------------------------------------

@app.post("/api/interview-questions")
def create_interview_questions(payload: InterviewRequest, request: Request):
    _require_api_auth(request)
    if _is_rate_limited(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests -- please wait a minute.")
    try:
        result = gemini_client.generate_json(
            system_instruction=prompts.INTERVIEW_SYSTEM_PROMPT,
            user_prompt=prompts.build_interview_prompt(
                payload.role, payload.company, payload.job_description
            ),
        )
    except gemini_client.GenerationError as exc:
        logger.warning("Interview generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    entry_id = history.save_entry("interview", payload.role, payload.company, result)
    return {"id": entry_id, "result": result}


@app.post("/api/resume")
def create_resume(payload: ResumeRequest, request: Request):
    _require_api_auth(request)
    if _is_rate_limited(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests -- please wait a minute.")
    try:
        resume_text = gemini_client.generate_text(
            system_instruction=prompts.RESUME_SYSTEM_PROMPT,
            user_prompt=prompts.build_resume_prompt(
                payload.role, payload.company, payload.job_description, payload.background
            ),
        )
    except gemini_client.GenerationError as exc:
        logger.warning("Resume generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    result = {"resume_text": resume_text}
    entry_id = history.save_entry("resume", payload.role, payload.company, result)
    return {"id": entry_id, "result": result}


@app.post("/api/cover-letter")
def create_cover_letter(payload: ResumeRequest, request: Request):
    """Same inputs as the resume writer (role, company, JD, background) --
    no separate form needed on the frontend."""
    _require_api_auth(request)
    if _is_rate_limited(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests -- please wait a minute.")
    try:
        letter_text = gemini_client.generate_text(
            system_instruction=prompts.COVER_LETTER_SYSTEM_PROMPT,
            user_prompt=prompts.build_cover_letter_prompt(
                payload.role, payload.company, payload.job_description, payload.background
            ),
        )
    except gemini_client.GenerationError as exc:
        logger.warning("Cover letter generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    result = {"letter_text": letter_text}
    entry_id = history.save_entry("cover_letter", payload.role, payload.company, result)
    return {"id": entry_id, "result": result}


# --- resume file upload + download --------------------------------------

@app.post("/api/extract-resume")
async def extract_resume(request: Request, file: UploadFile = File(...)):
    _require_api_auth(request)
    content = await file.read()
    try:
        text = resume_files.extract_text(file.filename, content)
    except resume_files.ResumeFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"text": text}


@app.get("/api/document/{entry_id}/docx")
def download_document_docx(entry_id: int, request: Request):
    _require_api_auth(request)
    entry = history.get_entry(entry_id)
    if not entry or entry["kind"] not in ("resume", "cover_letter"):
        raise HTTPException(status_code=404, detail="Not found")
    if entry["kind"] == "resume":
        text, filename = entry["result"]["resume_text"], "resume.docx"
    else:
        text, filename = entry["result"]["letter_text"], "cover-letter.docx"
    docx_bytes = resume_files.build_docx_from_text(text)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- job matching ---------------------------------------------------------

@app.post("/api/job-matches")
def find_job_matches(payload: JobMatchRequest, request: Request):
    _require_api_auth(request)
    if _is_rate_limited(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests -- please wait a minute.")
    try:
        query = gemini_client.generate_text(
            system_instruction=prompts.JOB_SEARCH_KEYWORDS_SYSTEM_PROMPT,
            user_prompt=prompts.build_job_search_keywords_prompt(payload.role, payload.resume_text),
            temperature=0.3,
        ).strip()
    except gemini_client.GenerationError as exc:
        logger.warning("Keyword extraction failed, falling back to role only: %s", exc)
        query = payload.role

    try:
        jobs = job_search.search_jobs(
            what=query, where=payload.location, country=payload.country, max_results=25
        )
    except job_search.JobSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    wanted_modes = set(payload.work_modes) or {"remote", "hybrid", "onsite"}
    filtered = [j for j in jobs if j["work_mode"] in wanted_modes]
    salary = job_search.estimate_salary(filtered or jobs)

    return {
        "search_query": query,
        "jobs": filtered,
        "total_before_filter": len(jobs),
        "salary_estimate": salary,
    }


# --- application tracker ---------------------------------------------------

@app.get("/api/tracker")
def list_tracked_jobs(request: Request):
    _require_api_auth(request)
    return {"jobs": tracker.list_jobs()}


@app.post("/api/tracker")
def track_job(payload: TrackJobRequest, request: Request):
    _require_api_auth(request)
    job_id = tracker.add_job(payload.model_dump())
    return {"id": job_id}


@app.patch("/api/tracker/{job_id}/status")
def set_job_status(job_id: int, payload: UpdateJobStatusRequest, request: Request):
    _require_api_auth(request)
    if payload.status not in tracker.VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of {tracker.VALID_STATUSES}")
    if not tracker.update_status(job_id, payload.status):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@app.patch("/api/tracker/{job_id}/notes")
def set_job_notes(job_id: int, payload: UpdateJobNotesRequest, request: Request):
    _require_api_auth(request)
    if not tracker.update_notes(job_id, payload.notes):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@app.delete("/api/tracker/{job_id}")
def remove_tracked_job(job_id: int, request: Request):
    _require_api_auth(request)
    if not tracker.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
