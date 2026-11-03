"""Guards for the dependency files Vercel installs (a merged line once broke the backend build)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "requirements.txt"
DEV = ROOT / "requirements-dev.txt"
SPEC = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]*(\[[A-Za-z0-9,_\-]+\])?([<>=!~]=?[A-Za-z0-9.*]+)?")
TEST_ONLY = {"pytest", "pytest-asyncio", "aiosqlite"}


def _packages(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.strip().startswith(("#", "-r"))]


def test_files_end_with_newline():
    for path in (REQ, DEV):
        assert path.read_text().endswith("\n"), f"{path.name} must end with a newline so appends don't merge lines"


def test_every_line_is_one_valid_requirement():
    for path in (REQ, DEV):
        for line in _packages(path):
            assert SPEC.fullmatch(line), f"{path.name}: suspicious requirement line {line!r}"


def test_no_duplicates():
    names = [re.split(r"[\[<>=!~]", l)[0].lower() for l in _packages(REQ)]
    assert len(names) == len(set(names))


def test_test_only_packages_stay_out_of_the_deployed_bundle():
    names = {re.split(r"[\[<>=!~]", l)[0].lower() for l in _packages(REQ)}
    assert not (names & TEST_ONLY), f"move {names & TEST_ONLY} to requirements-dev.txt"


def test_runtime_imports_used_by_new_modules_are_declared():
    names = {re.split(r"[\[<>=!~]", l)[0].lower() for l in _packages(REQ)}
    for needed in ("langchain-openai", "typesafe-sdk", "clerk-backend-api", "inngest", "langgraph"):
        assert needed in names
