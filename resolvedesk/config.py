import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
RUNTIME = Path(os.getenv("RESOLVEDESK_RUNTIME", ROOT / "runtime"))
RUNTIME.mkdir(parents=True, exist_ok=True)
DB = RUNTIME / "store.sqlite"
CHECKPOINTS = RUNTIME / "checkpoints.sqlite"
REPORTS = ROOT / "evals" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)


def agent_mode():
    return os.getenv("AGENT_MODE", "gemini")
