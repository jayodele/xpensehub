"""Tool implementations called by the application agent."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

APPLICATIONS_FILE = Path(__file__).parent / "applications.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Job search
# ---------------------------------------------------------------------------

def search_jobs(query: str, location: str = "London", max_results: int = 10) -> list[dict]:
    """Search Reed.co.uk for jobs matching *query* in *location*."""
    encoded_q = urllib.parse.quote_plus(query)
    encoded_loc = urllib.parse.quote_plus(location)
    url = f"https://www.reed.co.uk/jobs/{encoded_q}-jobs-in-{encoded_loc}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        return [{"error": f"Search request failed: {exc}"}]

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs: list[dict] = []

    for card in soup.select("article.job-result-card")[:max_results]:
        title_tag = card.select_one("h3.title a, h2.title a, a[data-id]")
        title = title_tag.get_text(strip=True) if title_tag else "Unknown"
        href = title_tag.get("href", "") if title_tag else ""
        job_url = f"https://www.reed.co.uk{href}" if href.startswith("/") else href

        company_tag = card.select_one(".employer, [data-qa='employer']")
        company = company_tag.get_text(strip=True) if company_tag else "Unknown"

        location_tag = card.select_one(".job-location, [data-qa='job-location']")
        loc = location_tag.get_text(strip=True) if location_tag else location

        salary_tag = card.select_one(".salary, [data-qa='salary']")
        salary = salary_tag.get_text(strip=True) if salary_tag else "Not specified"

        snippet_tag = card.select_one(".job-result-description, .description")
        snippet = snippet_tag.get_text(strip=True)[:300] if snippet_tag else ""

        job_id_match = re.search(r"/jobs/(\d+)/", job_url)
        job_id = job_id_match.group(1) if job_id_match else ""

        jobs.append({
            "id": job_id,
            "title": title,
            "company": company,
            "location": loc,
            "salary": salary,
            "url": job_url,
            "snippet": snippet,
        })

    return jobs


# ---------------------------------------------------------------------------
# Job details
# ---------------------------------------------------------------------------

def get_job_details(job_url: str) -> dict:
    """Fetch full job description from a Reed job posting URL."""
    try:
        resp = requests.get(job_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        return {"error": f"Failed to fetch job: {exc}"}

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.select_one("h1.job-header__title, h1[itemprop='title']")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

    company_tag = soup.select_one(".employer-preview__title, [itemprop='hiringOrganization'] [itemprop='name']")
    company = company_tag.get_text(strip=True) if company_tag else "Unknown"

    desc_tag = soup.select_one(
        "#job-description-container, .job-description, [itemprop='description']"
    )
    description = desc_tag.get_text(separator="\n", strip=True)[:4000] if desc_tag else "Not available"

    salary_tag = soup.select_one(".salary, [data-qa='salary']")
    salary = salary_tag.get_text(strip=True) if salary_tag else "Not specified"

    return {
        "title": title,
        "company": company,
        "salary": salary,
        "url": job_url,
        "description": description,
    }


# ---------------------------------------------------------------------------
# Cover letter generation helper (template — Claude fills in at agent level)
# ---------------------------------------------------------------------------

def build_cover_letter_prompt(job: dict, cv_text: str) -> str:
    return f"""You are writing a professional cover letter on behalf of Jerry Ayodele.

CV:
{cv_text}

Job Posting:
Title: {job.get('title')}
Company: {job.get('company')}
Salary: {job.get('salary', 'Not specified')}
Description:
{job.get('description', job.get('snippet', ''))}

Write a compelling, concise cover letter (3-4 paragraphs) tailored specifically to this role.
- Open by referencing the specific role and company.
- Highlight the 2-3 most relevant achievements from Jerry's CV that match the job requirements.
- Close with enthusiasm and a call to action.
- Tone: confident, professional, not generic.
- Do NOT use placeholders like [Your Name]. Use Jerry's actual details.
"""


# ---------------------------------------------------------------------------
# Application tracker
# ---------------------------------------------------------------------------

def _load_applications() -> list[dict]:
    if APPLICATIONS_FILE.exists():
        return json.loads(APPLICATIONS_FILE.read_text())
    return []


def _save_applications(apps: list[dict]) -> None:
    APPLICATIONS_FILE.write_text(json.dumps(apps, indent=2))


def save_application(
    job: dict,
    cover_letter: str,
    status: str = "cover_letter_ready",
) -> dict:
    """Persist an application record and return it."""
    apps = _load_applications()
    record: dict[str, Any] = {
        "id": job.get("id") or f"manual-{int(time.time())}",
        "applied_at": datetime.utcnow().isoformat(),
        "status": status,
        "job_title": job.get("title"),
        "company": job.get("company"),
        "salary": job.get("salary"),
        "url": job.get("url"),
        "cover_letter": cover_letter,
    }
    # Avoid duplicates by job id
    apps = [a for a in apps if a.get("id") != record["id"]]
    apps.append(record)
    _save_applications(apps)
    return record


def list_applications() -> list[dict]:
    return _load_applications()


# ---------------------------------------------------------------------------
# Tool schemas for Claude tool_use
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "search_jobs",
        "description": (
            "Search Reed.co.uk for Senior Product Manager / Senior Product Lead jobs in London. "
            "Returns a list of job postings with title, company, location, salary, URL, and snippet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'senior product manager'",
                },
                "location": {
                    "type": "string",
                    "description": "Location, default 'London'",
                    "default": "London",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max jobs to return (default 8)",
                    "default": 8,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_job_details",
        "description": "Fetch the full job description for a Reed.co.uk job URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_url": {
                    "type": "string",
                    "description": "Full URL of the Reed job posting",
                }
            },
            "required": ["job_url"],
        },
    },
    {
        "name": "save_application",
        "description": (
            "Save a completed application (job details + cover letter) to the tracker. "
            "Call this after writing the cover letter for each job."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job": {
                    "type": "object",
                    "description": "Job object with id, title, company, salary, url fields",
                },
                "cover_letter": {
                    "type": "string",
                    "description": "The tailored cover letter text",
                },
                "status": {
                    "type": "string",
                    "description": "Application status",
                    "default": "cover_letter_ready",
                },
            },
            "required": ["job", "cover_letter"],
        },
    },
    {
        "name": "list_applications",
        "description": "Return all saved applications from the tracker.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def dispatch(name: str, inputs: dict) -> Any:
    """Route a tool call by name to its implementation."""
    if name == "search_jobs":
        return search_jobs(**inputs)
    if name == "get_job_details":
        return get_job_details(**inputs)
    if name == "save_application":
        return save_application(**inputs)
    if name == "list_applications":
        return list_applications()
    raise ValueError(f"Unknown tool: {name}")
