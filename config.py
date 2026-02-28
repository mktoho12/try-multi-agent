import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384
WORKSPACE_DIR = Path(__file__).parent / "workspace_output"
MAX_ITERATIONS = 5

# Runtime Validation Gate
ENABLE_RUNTIME_VALIDATION = True
ENABLE_BROWSER_VALIDATION = True
CHROME_PATH = os.environ.get(
    "CHROME_PATH",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
CDP_PORT = 9222
BACKEND_PORT = 8000
FRONTEND_PORT = 3000
