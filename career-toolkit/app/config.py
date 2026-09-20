"""
Central configuration. Everything here is read from environment variables
(see .env.example) so nothing sensitive is hardcoded in the source.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# As of Sept 2026: Gemini 2.5 models (Pro/Flash/Flash-Lite) are scheduled to
# shut down on 16 Oct 2026. gemini-3.1-pro-preview is the current Pro-tier
# model at time of writing, but Google's "-preview" aliases change over
# time. If generation starts failing, check
# https://ai.google.dev/gemini-api/docs/models and update GEMINI_MODEL
# below (or in your .env) accordingly -- no code changes needed.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")

# --- Auth ---
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    # Falls back to a random key so the app still boots, but every restart
    # invalidates existing sessions. Set SECRET_KEY in .env for a real deploy.
    SECRET_KEY = secrets.token_hex(32)

# --- Server ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# --- Storage ---
DB_PATH = BASE_DIR / "data" / "history.db"

# --- Rate limiting (naive, in-memory, per worker process) ---
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

# --- Adzuna (job search + salary data) ---
# Free account: https://developer.adzuna.com/signup -- optional. The job
# matching feature just returns a clear error if these aren't set; nothing
# else in the app depends on them.
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_DEFAULT_COUNTRY = os.getenv("ADZUNA_DEFAULT_COUNTRY", "in")


def startup_warnings() -> list[str]:
    """Human-readable warnings to print once at startup."""
    warnings = []
    if not GEMINI_API_KEY:
        warnings.append("GEMINI_API_KEY is not set -- generation calls will fail. Add it to .env.")
    if not APP_PASSWORD:
        warnings.append("APP_PASSWORD is not set -- the dashboard is UNPROTECTED on the network. Set it in .env.")
    if not os.getenv("SECRET_KEY"):
        warnings.append("SECRET_KEY is not set -- a temporary one was generated; logins won't survive a restart.")
    return warnings
