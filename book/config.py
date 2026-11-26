"""Environment and path configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

load_dotenv(ROOT / ".env")


def has_env(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def require_env(name: str) -> str:
    """Return the value of an environment variable or raise a clear error."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing environment variable {name}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


# The SDK default is a 10-minute timeout with 2 retries; an overloaded model (Gemini 503s
# can hang for minutes) would stall a CI run for an hour before the fallback provider.
API_TIMEOUT = 120
API_RETRIES = 1


def openai_client():
    """OpenAI client from OPENAI_API_KEY; imported lazily so tests and dry runs need no key."""
    from openai import OpenAI

    return OpenAI(api_key=require_env("OPENAI_API_KEY"), timeout=API_TIMEOUT, max_retries=API_RETRIES)


def gemini_client():
    """Gemini through its OpenAI-compatible endpoint, so no extra package is needed."""
    from openai import OpenAI

    return OpenAI(
        api_key=require_env("GEMINI_API_KEY"),
        base_url=GEMINI_BASE_URL,
        timeout=API_TIMEOUT,
        max_retries=API_RETRIES,
    )


def output_dir_for(run_date: str) -> Path:
    """Return (and create) the output folder for a given ISO date."""
    path = OUTPUT_DIR / run_date
    path.mkdir(parents=True, exist_ok=True)
    return path
