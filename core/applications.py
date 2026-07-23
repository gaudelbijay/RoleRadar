"""Local, review-first job application preparation."""
from __future__ import annotations
import io
import re
from dataclasses import dataclass

MAX_CV_CHARS = 30_000

@dataclass(frozen=True)
class ApplicantProfile:
    full_name: str
    email: str
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    work_authorization: str = "Prefer not to answer"
    sponsorship: str = "Prefer not to answer"
    relocation: str = "Prefer not to answer"
    salary_expectation: str = ""

def extract_cv_text(filename: str, file_data: bytes) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(file_data)).pages)
    elif suffix == "docx":
        from docx import Document
        text = "\n".join(p.text for p in Document(io.BytesIO(file_data)).paragraphs)
    elif suffix in {"txt", "md"}:
        text = file_data.decode("utf-8", errors="replace")
    else:
        raise ValueError("Upload a PDF, DOCX, TXT, or Markdown CV.")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise ValueError("No readable text was found. Try a text-based PDF or DOCX file.")
    return text[:MAX_CV_CHARS]

def validate_profile(profile: ApplicantProfile) -> list[str]:
    errors = []
    if not profile.full_name.strip():
        errors.append("Full name is required.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", profile.email.strip()):
        errors.append("A valid email address is required.")
    for label, value in (("LinkedIn URL", profile.linkedin_url), ("Portfolio URL", profile.portfolio_url)):
        if value and not value.startswith(("https://", "http://")):
            errors.append(f"{label} must start with http:// or https://.")
    return errors

def _keywords(text: str) -> set[str]:
    stop = {"about", "after", "also", "and", "are", "been", "being", "can", "company", "from", "have", "into", "job", "more", "our", "role", "that", "the", "their", "they", "this", "with", "will", "work", "years", "you", "your"}
    return {t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", text.lower()) if t not in stop}

def prepare_application(job: dict, profile: ApplicantProfile, cv_text: str) -> dict:
    cv_words = _keywords(cv_text)
    job_words = _keywords(" ".join([str(job.get("title") or ""), str(job.get("description") or ""), " ".join(job.get("requirements") or [])]))
    overlap = sorted(cv_words & job_words, key=lambda x: (-len(x), x))[:14]
    skills = ", ".join(overlap[:8]) or "the relevant experience in my CV"
    company = str(job.get("company") or "your organization")
    title = str(job.get("title") or "this position")
    cover_letter = (f"Dear {company} hiring team,\n\nI am applying for the {title} position. My background includes {skills}, which aligns with the role's stated needs. I would welcome the opportunity to discuss how my experience can contribute to your team.\n\nI have attached my CV for the full details of my education and work history. Thank you for your consideration.\n\nSincerely,\n{profile.full_name}")
    answers = {"Full name": profile.full_name, "Email": profile.email, "Phone": profile.phone or "Not provided", "Current location": profile.location or "Not provided", "LinkedIn": profile.linkedin_url or "Not provided", "Portfolio": profile.portfolio_url or "Not provided", "Work authorization": profile.work_authorization, "Requires sponsorship": profile.sponsorship, "Open to relocation": profile.relocation, "Salary expectation": profile.salary_expectation or "Discuss during interview"}
    return {"job": job, "cover_letter": cover_letter, "suggested_answers": answers, "matched_cv_terms": overlap, "status": "Ready for review"}
