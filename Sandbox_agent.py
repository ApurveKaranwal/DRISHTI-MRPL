"""A secure local Python execution sandbox worker for engineering scripts and calculations.

Executes Python scripts in an isolated subprocess with timeout protection,
captures stdout/stderr, tracks execution time, saves generated plots/artifacts,
and enforces security AST scans to prevent dangerous system calls.
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


@dataclass(frozen=True)
class SandboxSettings:
    sandbox_dir: Path = Path(os.getenv("SANDBOX_DIR", "./outputs/sandbox"))
    timeout_seconds: float = float(os.getenv("SANDBOX_TIMEOUT", "30.0"))
    python_executable: str = sys.executable


class SecurityViolationError(RuntimeError):
    """Raised when script contains potentially harmful system operations."""
    pass


class SandboxExecutionError(RuntimeError):
    """Raised when code execution fails or times out."""
    pass


# Disallowed AST calls/modules to protect the workstation and enforce air-gap
BLOCKED_MODULES = {
    "pty", "winreg", "webbrowser", "http.server", "socket", "urllib.request",
    "requests", "http.client", "ftplib", "smtplib", "telnetlib", "asyncio.subprocess",
    "multiprocessing", "ctypes"
}
BLOCKED_CALLS = {
    "system", "popen", "spawn", "rmdir", "removedirs", "unlink", "kill",
    "shutdown", "format_drive", "fork", "execv", "execve"
}


class CodeSandboxWorker:
    """Executes Python code in an isolated environment and returns execution telemetry."""

    def __init__(self, settings: SandboxSettings | None = None) -> None:
        self.settings = settings or SandboxSettings()
        self.settings.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def _validate_ast_security(self, code: str) -> None:
        """Statically inspects Python code AST for prohibited calls before execution."""
        try:
            tree = ast.parse(code)
        except SyntaxError as err:
            raise SandboxExecutionError(f"Syntax error in script: {err}") from err

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in BLOCKED_MODULES:
                        raise SecurityViolationError(f"Prohibited module import: '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module in BLOCKED_MODULES:
                    raise SecurityViolationError(f"Prohibited module import: '{node.module}'")

            # Check function calls
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                if func_name in BLOCKED_CALLS:
                    raise SecurityViolationError(f"Security violation: Prohibited call '{func_name}'")

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

        # 2. Prepare temporary script file
        run_id = uuid.uuid4().hex[:8]
        safe_name = script_name or f"run_{run_id}.py"
        script_file = self.settings.sandbox_dir / safe_name
        
        # Ensure outputs/sandbox exists
        self.settings.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Snapshot existing files in sandbox_dir to detect newly created artifacts
        before_files = set(self.settings.sandbox_dir.iterdir())

        # Write script
        script_file.write_text(code, encoding="utf-8")

        # 3. Subprocess execution
        start_time = time.perf_counter()
        timed_out = False
        try:
            process = subprocess.run(
                [self.settings.python_executable, str(script_file)],
                capture_output=True,
                text=True,
                timeout=self.settings.timeout_seconds,
                cwd=str(Path.cwd()),  # Run relative to project root so outputs/ paths resolve
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"}
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
