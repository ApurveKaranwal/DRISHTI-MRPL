"""A secure local Python execution sandbox worker for engineering scripts and calculations.

Executes Python scripts in an isolated subprocess with timeout protection,
captures stdout/stderr, tracks execution time, saves generated plots/artifacts,
and enforces security AST scans to prevent dangerous system calls.

Security model:
  - WHITELIST approach: only explicitly allowed modules/builtins may be used
  - Script names are sanitized to prevent path traversal
  - Subprocess runs with stripped environment (no secrets/tokens)
  - Subprocess CWD is restricted to the sandbox directory
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _detect_python_executable() -> str:
    """Detects virtual environment python executable or falls back to sys.executable."""
    venv_py = Path(__file__).parent.absolute() / "venv" / "bin" / "python"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


@dataclass(frozen=True)
class SandboxSettings:
    sandbox_dir: Path = Path(os.getenv("SANDBOX_DIR", "./outputs/sandbox"))
    timeout_seconds: float = float(os.getenv("SANDBOX_TIMEOUT", "30.0"))
    python_executable: str = _detect_python_executable()


class SecurityViolationError(RuntimeError):
    """Raised when script contains potentially harmful system operations."""
    pass


class SandboxExecutionError(RuntimeError):
    """Raised when code execution fails or times out."""
    pass


# ── Security Whitelist Configuration ──────────────────────────────────────────
# Only modules in this set may be imported. Everything else is blocked.
ALLOWED_MODULES = {
    # Standard library — safe, no I/O or system mutation
    "math", "cmath", "decimal", "fractions", "statistics", "random",
    "itertools", "functools", "operator", "collections", "heapq", "bisect",
    "copy", "pprint", "textwrap", "string", "re", "struct", "array",
    "datetime", "time", "calendar", "zoneinfo",
    "json", "csv", "io", "base64", "hashlib", "hmac",
    "dataclasses", "typing", "types", "abc", "enum", "contextlib",
    "warnings", "traceback", "logging", "numbers",
    "pathlib",  # read-only path construction
    # Scientific / engineering — the primary use-case
    "numpy", "pandas", "scipy", "scipy.optimize", "scipy.interpolate",
    "scipy.integrate", "scipy.signal", "scipy.stats", "scipy.linalg",
    "scipy.spatial", "scipy.constants",
    "matplotlib", "matplotlib.pyplot", "matplotlib.figure",
    "matplotlib.ticker", "matplotlib.dates", "matplotlib.patches",
    "matplotlib.colors", "matplotlib.cm",
    "seaborn", "plotly", "plotly.express", "plotly.graph_objects",
    "sklearn", "sklearn.linear_model", "sklearn.preprocessing",
    "sklearn.metrics", "sklearn.cluster",
    "sympy",
    "openpyxl",
    # CoolProp for thermo engineering calculations
    "CoolProp", "CoolProp.CoolProp",
}

# Builtin function names that MUST NOT appear as bare calls
BLOCKED_BUILTINS = {
    "exec", "eval", "compile", "__import__", "getattr", "setattr",
    "delattr", "globals", "locals", "vars", "dir",
    "breakpoint", "exit", "quit",
}

# Attribute-level calls that are always blocked regardless of the receiver
BLOCKED_ATTR_CALLS = {
    "system", "popen", "spawn", "rmdir", "removedirs", "unlink", "kill",
    "shutdown", "fork", "execv", "execve", "remove", "rename", "replace",
    "write", "writelines", "truncate",  # block file writes via handles
    "Popen", "run", "call", "check_output", "check_call",  # subprocess.*
}

# Environment variable keys stripped from the subprocess (secrets, tokens, etc.)
_DANGEROUS_ENV_PREFIXES = (
    "SECRET", "TOKEN", "PASSWORD", "API_KEY", "AWS_", "AZURE_", "GCP_",
    "OPENAI", "ANTHROPIC", "HF_TOKEN", "HUGGING", "GITHUB_TOKEN",
    "DATABASE_URL", "REDIS_URL", "MONGO", "POSTGRES",
)


def _safe_env() -> dict[str, str]:
    """Returns a stripped copy of os.environ with secrets and dangerous vars removed."""
    safe = {}
    for key, val in os.environ.items():
        key_upper = key.upper()
        if any(key_upper.startswith(prefix) or key_upper == prefix for prefix in _DANGEROUS_ENV_PREFIXES):
            continue
        safe[key] = val
    # Force matplotlib to non-interactive backend and UTF-8
    safe["MPLBACKEND"] = "Agg"
    safe["PYTHONIOENCODING"] = "utf-8"
    return safe


class CodeSandboxWorker:
    """Executes Python code in an isolated environment and returns execution telemetry."""

    def __init__(self, settings: SandboxSettings | None = None) -> None:
        self.settings = settings or SandboxSettings()
        self.settings.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def _validate_ast_security(self, code: str) -> None:
        """Statically inspects Python code AST for prohibited calls before execution.

        Uses a WHITELIST approach:
          - Imports: only modules in ALLOWED_MODULES are permitted
          - Calls: bare calls to BLOCKED_BUILTINS are rejected
          - Attribute calls: methods in BLOCKED_ATTR_CALLS are rejected
          - open() as a bare builtin is explicitly blocked
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as err:
            raise SandboxExecutionError(f"Syntax error in script: {err}") from err

        for node in ast.walk(tree):
            # ── Import validation (whitelist) ──
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_module = alias.name.split(".")[0]
                    if alias.name not in ALLOWED_MODULES and top_module not in ALLOWED_MODULES:
                        raise SecurityViolationError(
                            f"Prohibited module import: '{alias.name}'. "
                            f"Only whitelisted scientific/engineering modules are allowed."
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_module = node.module.split(".")[0]
                    if node.module not in ALLOWED_MODULES and top_module not in ALLOWED_MODULES:
                        raise SecurityViolationError(
                            f"Prohibited module import: '{node.module}'. "
                            f"Only whitelisted scientific/engineering modules are allowed."
                        )

            # ── Call validation ──
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    # Block dangerous builtins
                    if func_name in BLOCKED_BUILTINS:
                        raise SecurityViolationError(
                            f"Security violation: Prohibited builtin call '{func_name}'"
                        )
                    # Block bare open() — file I/O from user scripts
                    if func_name == "open":
                        raise SecurityViolationError(
                            "Security violation: Direct file I/O via open() is not allowed. "
                            "Use pandas or numpy for data loading."
                        )
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                    if func_name in BLOCKED_ATTR_CALLS:
                        raise SecurityViolationError(
                            f"Security violation: Prohibited method call '.{func_name}()'"
                        )

    @staticmethod
    def _sanitize_script_name(name: str | None, run_id: str) -> str:
        """Sanitizes script_name to prevent path traversal and injection.

        Returns a safe basename with only alphanumerics, underscores, hyphens, and dots.
        """
        if not name:
            return f"run_{run_id}.py"
        # Strip any directory components — use only the final filename part
        base = Path(name).name
        # Remove any characters that aren't safe
        safe = "".join(c for c in base if c.isalnum() or c in ("_", "-", "."))
        # Ensure it ends with .py
        if not safe.endswith(".py"):
            safe += ".py"
        # Fallback if empty after sanitization
        if safe == ".py":
            safe = f"run_{run_id}.py"
        return safe

    def execute_code(
        self,
        code: str,
        script_name: str | None = None,
        save_plot: bool = True
    ) -> dict[str, Any]:
        """Safely runs the code string, capturing output and output artifacts."""
        if not code.strip():
            raise ValueError("No code provided for sandbox execution.")

        # 1. Pre-execution static security scan
        self._validate_ast_security(code)

        # 2. Prepare temporary script file (sanitized name, no traversal)
        run_id = uuid.uuid4().hex[:8]
        safe_name = self._sanitize_script_name(script_name, run_id)
        script_file = self.settings.sandbox_dir / safe_name

        # Ensure sandbox directory exists
        self.settings.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Verify the resolved path is inside sandbox_dir (defense in depth)
        resolved_script = script_file.resolve()
        resolved_sandbox = self.settings.sandbox_dir.resolve()
        if not str(resolved_script).startswith(str(resolved_sandbox)):
            raise SecurityViolationError(
                "Script path escapes sandbox directory. Possible path traversal attack."
            )

        # Snapshot existing files in sandbox_dir to detect newly created artifacts
        before_files = set(self.settings.sandbox_dir.iterdir())

        # Write script
        script_file.write_text(code, encoding="utf-8")

        # 3. Subprocess execution with stripped env and sandbox-restricted CWD
        start_time = time.perf_counter()
        timed_out = False
        try:
            process = subprocess.run(
                [self.settings.python_executable, str(resolved_script)],
                capture_output=True,
                text=True,
                timeout=self.settings.timeout_seconds,
                cwd=str(self.settings.sandbox_dir.resolve()),  # Restrict CWD to sandbox
                env=_safe_env(),  # Stripped environment — no secrets
            )
            stdout = process.stdout
            stderr = process.stderr
            returncode = process.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
            stderr = f"Execution timed out after {self.settings.timeout_seconds} seconds."
            returncode = -1
        except Exception as exc:
            stdout = ""
            stderr = f"Subprocess launch failed: {exc}"
            returncode = -1
        finally:
            elapsed_time = round(time.perf_counter() - start_time, 3)

        # 4. Detect newly created artifact files (plots, csv, etc.)
        after_files = set(self.settings.sandbox_dir.iterdir())
        new_files = [str(f.resolve()) for f in (after_files - before_files) if f.name != safe_name]

        return {
            "success": returncode == 0 and not timed_out,
            "returncode": returncode,
            "timed_out": timed_out,
            "execution_time_seconds": elapsed_time,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "script_path": str(script_file.resolve()),
            "generated_files": new_files,
            "artifacts": new_files,
            "run_id": run_id,
        }
