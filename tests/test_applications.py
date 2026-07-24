import io

import pytest
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE

from core.applications import (
    ApplicantProfile,
    extract_cv_text,
    prepare_application,
    validate_profile,
)


def test_extract_plain_text_cv():
    assert extract_cv_text("resume.txt", b"Python robotics engineer") == (
        "Python robotics engineer"
    )


def test_empty_cv_is_rejected():
    with pytest.raises(ValueError, match="No readable text"):
        extract_cv_text("resume.txt", b"  \n")


def test_docx_embedded_hyperlink_is_preserved():
    document = Document()
    document.add_paragraph("Portfolio")
    document.part.rels.add_relationship(
        RELATIONSHIP_TYPE.HYPERLINK,
        "https://portfolio.example.com/work",
        "rIdPortfolio",
        is_external=True,
    )
    buffer = io.BytesIO()
    document.save(buffer)

    text = extract_cv_text("resume.docx", buffer.getvalue())

    assert "Portfolio" in text
    assert "https://portfolio.example.com/work" in text


def test_profile_validation_requires_name_email_and_http_urls():
    profile = ApplicantProfile("", "invalid", linkedin_url="linkedin.com/test")
    errors = validate_profile(profile)

    assert "Full name is required." in errors
    assert "A valid email address is required." in errors
    assert "LinkedIn URL must start with http:// or https://." in errors


def test_application_draft_uses_only_cv_overlap():
    profile = ApplicantProfile("Alex Example", "alex@example.com")
    job = {
        "title": "Robotics Engineer",
        "company": "Example Robotics",
        "description": "Python ROS motion planning",
        "requirements": ["Python and ROS"],
    }

    draft = prepare_application(job, profile, "Python controls research")

    assert "python" in draft["matched_cv_terms"]
    assert "Alex Example" in draft["cover_letter"]
    assert "ROS" not in draft["matched_cv_terms"]
    assert draft["status"] == "Ready for review"
