"""Los tests corren SIEMPRE en modo mock (sin IA) y con una BD SQLite temporal."""

import os
import tempfile
from pathlib import Path

_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["LLM_PROVIDERS"] = "mock"
os.environ["GOOGLE_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["JWT_SECRET"] = "test-secret-con-longitud-suficiente-32b"
os.environ["VERIFY_GITHUB"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture(scope="session", autouse=True)
def _db():
    from app.infrastructure.db import init_db

    init_db()


@pytest.fixture
def cv_template() -> bytes:
    return (SAMPLES / "cv_plantilla_laura.txt").read_bytes()


@pytest.fixture
def cv_free() -> bytes:
    return (SAMPLES / "cv_libre_andres.txt").read_bytes()


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES
