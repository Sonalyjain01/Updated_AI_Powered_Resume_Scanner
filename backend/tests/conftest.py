"""Shared fixtures: a fake AI provider and an in-memory MongoDB. No network, no real key."""
import io
import json
import os

# Set before any app module is imported. load_dotenv never overrides existing values,
# so a developer's real .env cannot leak into the tests.
os.environ["EMERGENT_LLM_KEY"] = "test-key-not-real"
os.environ["DB_NAME"] = "resume_scanner_test"
os.environ["OCR_ENGINE"] = "none"  # tests that need OCR opt in explicitly
os.environ["CLAMAV_ENABLED"] = "false"
os.environ["STORAGE_BACKEND"] = "none"  # tests that need storage pass their own
os.environ["AUTH_REQUIRED"] = "false"  # account tests turn it on themselves
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["BACKUP_DIR"] = ""
os.environ["JOB_WORKERS"] = "0"  # tests run jobs themselves; a few opt in to real workers
os.environ.pop("CORS_ORIGINS", None)

import docx
import fitz
import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

import ai_processor as ai_processor_module
import database as database_module
from llm_provider import LLMProvider
from storage import LocalFileStorage
from virus_scan import MalwareDetected, ScannerUnavailable, VirusScanner

JOB_DESCRIPTION = (
    "We are hiring a backend engineer with strong Python, FastAPI and MongoDB experience "
    "to design and run production APIs."
)
RESUME_TEXT = (
    "Jane Doe. Backend engineer with six years of experience building Python and FastAPI services. "
    "Led a team of four, designed MongoDB schemas and deployed on AWS. BSc Computer Science."
)

GOOD_EXTRACTION = json.dumps({"skills": ["python"], "education": ["BSc"], "experience": ["dev"]})
def match_reply(skills=82, experience=82, education=82, required=None, summary="ok"):
    """A model reply for the scoring step; the overall score is computed by the app"""
    return json.dumps({
        "skills_score": skills,
        "experience_score": experience,
        "education_score": education,
        "required_skills": required if required is not None else [
            {"skill": "python", "found": True, "evidence": "six years of Python"},
            {"skill": "kubernetes", "found": False, "evidence": ""},
        ],
        "analysis_summary": summary,
    })


GOOD_MATCH = match_reply()  # equal ratings, so any weights give 82


class FakeProvider(LLMProvider):
    """Returns canned replies in order, or a good default reply for each kind of prompt."""

    name = "fake"
    model = "gpt-4o"  # a priced model, so cost accounting is exercised

    def __init__(self, replies=None):
        self.replies = list(replies) if replies is not None else None
        self.calls = []  # (prompt, request_id)

    async def complete(self, prompt, system_message, request_id=None):
        self.calls.append((prompt, request_id))
        if self.replies is not None:
            reply = self.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        if "Respond with 'AI Service Connected'" in prompt:
            return "AI Service Connected"
        if "skills_score" in prompt:
            return GOOD_MATCH
        return json.dumps({"skills": ["python", "fastapi"], "education": ["BSc"], "experience": ["Backend engineer"]})


class FakeScanner(VirusScanner):
    """Clean by default; set `verdict` to a signature name, or to an Exception, to change that"""

    name = "fake"

    def __init__(self, verdict=None):
        self.verdict = verdict
        self.scanned = []

    async def scan(self, data):
        self.scanned.append(data)
        if isinstance(self.verdict, Exception):
            raise self.verdict
        if self.verdict:
            raise MalwareDetected(self.verdict)


def make_scanned_pdf(text: str = RESUME_TEXT) -> bytes:
    """A PDF whose only content is a picture of the text, like a scanner would produce"""
    source = fitz.open()
    page = source.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 550, 800), text, fontsize=14)
    png = page.get_pixmap(dpi=150).tobytes("png")
    scanned = fitz.open()
    new_page = scanned.new_page()
    new_page.insert_image(new_page.rect, stream=png)
    return scanned.tobytes()


def make_pdf(text: str = RESUME_TEXT) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 550, 800), text, fontsize=11)
    return pdf.tobytes()


def make_encrypted_pdf() -> bytes:
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), RESUME_TEXT)
    return pdf.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")


def make_docx(text: str = RESUME_TEXT) -> bytes:
    document = docx.Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
async def test_db(monkeypatch):
    """The real Database class connected to an in-memory MongoDB, migrations included"""
    monkeypatch.setattr(database_module, "AsyncIOMotorClient", AsyncMongoMockClient)
    db = database_module.Database()
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
def fake_scanner():
    return FakeScanner()


@pytest.fixture
def storage(tmp_path):
    return LocalFileStorage(tmp_path / "originals")


@pytest.fixture
def client(monkeypatch, fake_provider, fake_scanner, storage):
    """The real FastAPI app with a fake AI provider, fake virus scanner, temp-folder storage
    and an in-memory database"""
    monkeypatch.setattr(database_module, "AsyncIOMotorClient", AsyncMongoMockClient)
    monkeypatch.setattr(ai_processor_module, "get_llm_provider", lambda: fake_provider)
    import server  # imported late so the env above is already set
    monkeypatch.setattr(server, "get_virus_scanner", lambda: fake_scanner)
    monkeypatch.setattr(server, "get_storage", lambda: storage)

    with TestClient(server.app) as test_client:
        fake_provider.calls.clear()  # drop the startup health-check call
        yield test_client
