"""
Adzuna job search integration (https://developer.adzuna.com). Uses only the
standard library for HTTP (urllib) to avoid adding a dependency -- this is a
low-traffic, single-user tool, so a blocking call inside a sync FastAPI route
(which FastAPI already runs in a thread pool) is a fine trade for one less
package on a small server.

Free Adzuna accounts are rate-limited (roughly 25 calls/minute, 250/day at
signup time -- confirm current limits on your account page), so this module
makes exactly one search call per job-match request and derives the salary
estimate from those same results rather than making a second call.
"""
import json
import logging
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

from . import config

logger = logging.getLogger("career_toolkit.jobs")

BASE_URL = "https://api.adzuna.com/v1/api/jobs"

_HYBRID_HINTS = ("hybrid",)
_REMOTE_HINTS = ("remote", "work from home", "work-from-home", "wfh", "fully remote", "telecommute")


class JobSearchError(RuntimeError):
    """Raised when the job search API isn't configured or fails."""


def _infer_work_mode(title: str, description: str) -> str:
    """Best-effort tag from listing text. Adzuna has no dedicated remote/
    hybrid filter, so this is inferred, not guaranteed -- shown as such in
    the UI."""
    text = f"{title} {description}".lower()
    if any(h in text for h in _HYBRID_HINTS):
        return "hybrid"
    if any(h in text for h in _REMOTE_HINTS):
        return "remote"
    return "onsite"


def _request(path: str, params: dict) -> dict:
    if not config.ADZUNA_APP_ID or not config.ADZUNA_APP_KEY:
        raise JobSearchError(
            "Job search isn't set up yet -- get a free Adzuna app_id/app_key at "
            "https://developer.adzuna.com/signup and add them to .env as "
            "ADZUNA_APP_ID / ADZUNA_APP_KEY."
        )
    query = {
        "app_id": config.ADZUNA_APP_ID,
        "app_key": config.ADZUNA_APP_KEY,
        "content-type": "application/json",
        **params,
    }
    url = f"{BASE_URL}/{path}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        logger.warning("Adzuna HTTP %s: %s", exc.code, body)
        if exc.code == 401:
            raise JobSearchError(
                "Adzuna rejected the credentials -- double check ADZUNA_APP_ID/ADZUNA_APP_KEY in .env."
            ) from exc
        if exc.code == 429:
            raise JobSearchError("Adzuna rate limit hit -- wait a bit and try again.") from exc
        raise JobSearchError(f"Adzuna request failed (HTTP {exc.code}).") from exc
    except URLError as exc:
        raise JobSearchError(f"Could not reach Adzuna: {exc.reason}") from exc


def search_jobs(what: str, where: str = "", country: str = "in", max_results: int = 20) -> list[dict]:
    """Search live job postings. `country` is a two-letter Adzuna country
    code (in, gb, us, au, ca, nz, de, fr, pl, br, at, za, sg and others --
    check developer.adzuna.com for the current list; note Ireland and the
    UAE do not appear to be covered as of this writing)."""
    country = (country or config.ADZUNA_DEFAULT_COUNTRY or "in").lower().strip()
    params = {"results_per_page": max(1, min(max_results, 50)), "what": what}
    if where:
        params["where"] = where
    data = _request(f"{country}/search/1", params)

    jobs = []
    for item in data.get("results", []):
        title = item.get("title", "") or ""
        description = item.get("description", "") or ""
        jobs.append({
            "id": item.get("id"),
            "title": title,
            "company": (item.get("company") or {}).get("display_name") or "Unknown company",
            "location": (item.get("location") or {}).get("display_name") or "",
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "salary_is_predicted": bool(int(item.get("salary_is_predicted") or 0)),
            "url": item.get("redirect_url", ""),
            "description_snippet": description[:280],
            "work_mode": _infer_work_mode(title, description),
            "created": item.get("created", ""),
        })
    return jobs


def estimate_salary(jobs: list[dict]) -> dict | None:
    """Aggregate salary_min/max across whichever matched postings actually
    disclosed a salary. Returns None if none did (common in markets like
    India, where salary disclosure is less standard) rather than guessing."""
    priced = [j for j in jobs if j.get("salary_min") and j.get("salary_max")]
    if not priced:
        return None
    mins = [j["salary_min"] for j in priced]
    maxes = [j["salary_max"] for j in priced]
    midpoints = [(j["salary_min"] + j["salary_max"]) / 2 for j in priced]
    return {
        "low": round(min(mins)),
        "high": round(max(maxes)),
        "average": round(sum(midpoints) / len(midpoints)),
        "based_on": len(priced),
        "out_of": len(jobs),
        "any_predicted": any(j["salary_is_predicted"] for j in priced),
    }
