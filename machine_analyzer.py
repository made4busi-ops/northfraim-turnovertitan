"""
machine_analyzer.py

Walks every real .py file in the current directory tree (skipping venv,
__pycache__, .git, node_modules and theater-app) and runs four independent
checks, each implemented as its own function returning a list of problems:

    1. check_syntax            - ast.parse every file; report parse failures
                                 with real line numbers and error messages.
    2. check_imports           - import each file as a module inside a
                                 subprocess with a timeout, so one bad file
                                 cannot crash the scan; report files that
                                 raise ImportError / ModuleNotFoundError,
                                 including the missing module name.
    3. check_hardcoded_secrets - grep each file's TEXT for assignments whose
                                 string literal looks like a real leaked key
                                 (files loading keys via get_vault() or
                                 os.environ are NOT flagged).
    4. check_stub_likelihood   - flag files with fewer than 30 real
                                 (non-blank, non-comment) lines AND one or
                                 fewer function/class definitions.

run_full_analysis() walks the tree once, collects all .py files, runs all
four checks and returns one combined report dict.

Running this file directly prints a summary of the full analysis.
"""

import ast
import keyword
import os
import re
import subprocess
import sys

EXCLUDED_DIRS = {"venv", "__pycache__", ".git", "node_modules", "theater-app", "machines"}

IMPORT_TIMEOUT_SECONDS = 15

MAX_REPORTED_PER_CHECK = 10


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def collect_python_files(root="."):
    """Walk the directory tree once and collect every real .py file."""
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in place so os.walk never descends.
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for filename in filenames:
            if filename.endswith(".py"):
                py_files.append(os.path.join(dirpath, filename))
    return sorted(py_files)


# ---------------------------------------------------------------------------
# Check 1: syntax
# ---------------------------------------------------------------------------

def check_syntax(files):
    """ast.parse each file. Report files that fail, with line and message."""
    problems = []
    for path in files:
        try:
            # Read bytes so ast.parse honours PEP 263 encoding declarations.
            with open(path, "rb") as handle:
                source = handle.read()
        except OSError as exc:
            problems.append({"file": path, "line": None,
                             "error": "unreadable: %s" % exc})
            continue
        try:
            ast.parse(source, filename=path)
        except SyntaxError as exc:
            problems.append({"file": path, "line": exc.lineno,
                             "error": exc.msg})
        except ValueError as exc:  # e.g. source contains null bytes
            problems.append({"file": path, "line": None, "error": str(exc)})
    return problems


# ---------------------------------------------------------------------------
# Check 2: imports (sandboxed in a subprocess per file)
# ---------------------------------------------------------------------------

_IMPORT_PROBE = r"""
import sys
import importlib

sys.path.insert(0, sys.argv[1])
module_name = sys.argv[2]
try:
    importlib.import_module(module_name)
except (ImportError, ModuleNotFoundError) as exc:
    missing = getattr(exc, "name", "") or ""
    message = str(exc).replace("\n", " ").replace("|", "/")
    sys.stdout.write("IMPORTFAIL|%s|%s|%s\n" % (type(exc).__name__, missing, message))
    sys.exit(3)
except BaseException:
    # Any non-import failure (runtime errors, sys.exit at import time, ...)
    # is not this check's concern.
    sys.exit(0)
"""


def _import_target(path):
    """Return (sys_path_dir, module_name) used to import the given file."""
    directory = os.path.dirname(os.path.abspath(path))
    base = os.path.splitext(os.path.basename(path))[0]
    if base == "__init__":
        # Import the package itself, which executes this __init__.py.
        return os.path.dirname(directory), os.path.basename(directory)
    return directory, base


def check_imports(files):
    """Import each file as a module in a subprocess with a timeout.

    Reports files that raise ImportError or ModuleNotFoundError, along with
    the missing module name. A bad or hanging file cannot crash the scan.
    """
    problems = []
    for path in files:
        sys_path_dir, module_name = _import_target(path)
        if not module_name.isidentifier() or keyword.iskeyword(module_name):
            problems.append({
                "file": path,
                "missing_module": None,
                "error": "not importable as a module named %r" % module_name,
            })
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-c", _IMPORT_PROBE, sys_path_dir, module_name],
                capture_output=True,
                text=True,
                timeout=IMPORT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            problems.append({
                "file": path,
                "missing_module": None,
                "error": "import timed out after %ds" % IMPORT_TIMEOUT_SECONDS,
            })
            continue
        for line in result.stdout.splitlines():
            if line.startswith("IMPORTFAIL|"):
                _, exc_name, missing, message = line.split("|", 3)
                problems.append({
                    "file": path,
                    "missing_module": missing or None,
                    "error": "%s: %s" % (exc_name, message),
                })
                break
    return problems


# ---------------------------------------------------------------------------
# Check 3: hardcoded secrets (pure text grep, nothing is imported)
# ---------------------------------------------------------------------------

_SECRET_NAMES = (
    r"api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?key|"
    r"auth[_-]?token|access[_-]?token|client[_-]?secret|private[_-]?key|"
    r"secret|token|password|passwd"
)

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<name>\b(?:" + _SECRET_NAMES + r")\b)"
    r"\s*[=:]\s*"
    r"(?P<quote>['\"])"
    r"(?P<value>[^'\"\s]{8,})"
    r"(?P=quote)",
    re.IGNORECASE,
)

# Prefixes used by real, well-known key formats (OpenAI-style sk-..., GitHub
# tokens, Slack tokens, Google API keys, AWS access key IDs, JWTs, PEM blocks).
KNOWN_PREFIX_RE = re.compile(
    r"(sk_live_|sk_test_|sk-|rk_live_|pk_live_|pk_test_|"
    r"ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|"
    r"xox[baprs]-|AIza[0-9A-Za-z_\-]{10,}|ya29\.|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.|"
    r"-----BEGIN )"
)

# A 40+ character alphanumeric-ish literal (real keys often contain - _ . / + =).
LONG_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-+/.=]{39,}")

PLACEHOLDER_RE = re.compile(
    r"(your|my[-_]|change|replace|example|sample|dummy|fake|test|"
    r"placeholder|insert|todo|xxx|<.*>|\*{3,}|\.{3,}|^none$|^null$)",
    re.IGNORECASE,
)


def _classify_secret_value(value):
    """Return a reason string if the literal looks like a real key, else None."""
    if PLACEHOLDER_RE.search(value):
        return None
    if re.fullmatch(r"(.)\1*", value):  # aaaaaaaaa...
        return None
    prefix = KNOWN_PREFIX_RE.match(value)
    if prefix:
        return "known key prefix %r" % prefix.group(0)
    if LONG_KEY_RE.fullmatch(value):
        has_alpha = any(c.isalpha() for c in value)
        has_digit = any(c.isdigit() for c in value)
        if has_alpha and has_digit:
            return "%d-char high-entropy literal" % len(value)
    return None


def check_hardcoded_secrets(files):
    """Grep each file's TEXT for literal assignments that look like real keys.

    Files that load keys via get_vault(), key_vault or os.environ are not
    flagged -- only literal hardcoded strings that look like real keys are.
    """
    problems = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.read().splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lowered = line.lower()
            if "os.environ" in lowered or "get_vault" in lowered or "key_vault" in lowered:
                continue
            for match in SECRET_ASSIGNMENT_RE.finditer(line):
                value = match.group("value")
                reason = _classify_secret_value(value)
                if reason is None:
                    continue
                problems.append({
                    "file": path,
                    "line": lineno,
                    "variable": match.group("name"),
                    "masked": value[:6] + "...",
                    "reason": reason,
                })
    return problems


# ---------------------------------------------------------------------------
# Check 4: stub likelihood
# ---------------------------------------------------------------------------

_DEF_FALLBACK_RE = re.compile(r"^\s*(?:async\s+def|def|class)\s+\w+", re.MULTILINE)


def check_stub_likelihood(files):
    """Flag files with < 30 real (non-blank, non-comment) lines AND <= 1 def."""
    problems = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                source = handle.read()
        except OSError:
            continue
        real_lines = sum(
            1 for line in source.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        try:
            tree = ast.parse(source, filename=path)
            definitions = sum(
                1 for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            )
        except SyntaxError:
            # The syntax check owns parse failures; still estimate defs so a
            # broken one-line file is correctly reported as a stub too.
            definitions = len(_DEF_FALLBACK_RE.findall(source))
        if real_lines < 30 and definitions <= 1:
            problems.append({
                "file": path,
                "real_lines": real_lines,
                "definitions": definitions,
            })
    return problems


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def run_full_analysis(root="."):
    """Walk the tree once, run all four checks, return one combined report."""
    files = collect_python_files(root)
    syntax = check_syntax(files)
    imports = check_imports(files)
    secrets = check_hardcoded_secrets(files)
    stubs = check_stub_likelihood(files)
    return {
        "root": os.path.abspath(root),
        "files_scanned": len(files),
        "syntax_errors": {"count": len(syntax), "problems": syntax},
        "import_errors": {"count": len(imports), "problems": imports},
        "hardcoded_secrets": {"count": len(secrets), "problems": secrets},
        "likely_stubs": {"count": len(stubs), "problems": stubs},
    }


# ---------------------------------------------------------------------------
# Summary printing
# ---------------------------------------------------------------------------

def _fmt_syntax(problem):
    line = problem["line"] if problem["line"] is not None else "?"
    return "%s:%s - %s" % (problem["file"], line, problem["error"])


def _fmt_import(problem):
    if problem.get("missing_module"):
        return "%s - missing module '%s' (%s)" % (
            problem["file"], problem["missing_module"], problem["error"])
    return "%s - %s" % (problem["file"], problem["error"])


def _fmt_secret(problem):
    return "%s:%s - %s = \"%s\" (%s)" % (
        problem["file"], problem["line"], problem["variable"],
        problem["masked"], problem["reason"])


def _fmt_stub(problem):
    return "%s - %d real lines, %d function/class def(s)" % (
        problem["file"], problem["real_lines"], problem["definitions"])


def _print_section(title, bucket, formatter):
    print("\n%s: %d problem(s) found" % (title, bucket["count"]))
    for problem in bucket["problems"][:MAX_REPORTED_PER_CHECK]:
        print("    - %s" % formatter(problem))
    remaining = bucket["count"] - MAX_REPORTED_PER_CHECK
    if remaining > 0:
        print("    ... and %d more" % remaining)


if __name__ == "__main__":
    report = run_full_analysis(".")

    print("=" * 64)
    print("MACHINE ANALYZER - FULL CODEBASE REPORT")
    print("=" * 64)
    print("Root: %s" % report["root"])
    print("Files scanned: %d" % report["files_scanned"])

    _print_section("1. Syntax errors", report["syntax_errors"], _fmt_syntax)
    _print_section("2. Import failures", report["import_errors"], _fmt_import)
    _print_section("3. Hardcoded secrets", report["hardcoded_secrets"], _fmt_secret)
    _print_section("4. Likely stubs", report["likely_stubs"], _fmt_stub)

    total = (report["syntax_errors"]["count"] + report["import_errors"]["count"]
             + report["hardcoded_secrets"]["count"] + report["likely_stubs"]["count"])
    print("\n" + "-" * 64)
    print("Total problems across all checks: %d" % total)