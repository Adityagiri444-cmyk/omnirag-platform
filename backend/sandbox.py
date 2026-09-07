import subprocess
import sys
import json
import tempfile
import os

TIMEOUT_SECONDS = 5

# Only these modules are importable inside the sandbox - no os, sys, socket, subprocess, etc.
ALLOWED_MODULES = {"math", "statistics", "re", "json", "collections"}

SANDBOX_TEMPLATE = '''
import builtins

_allowed_builtins = {{
    "print": print, "len": len, "range": range, "sum": sum, "min": min, "max": max,
    "sorted": sorted, "enumerate": enumerate, "zip": zip, "abs": abs, "round": round,
    "int": int, "float": float, "str": str, "list": list, "dict": dict, "set": set,
    "tuple": tuple, "bool": bool, "isinstance": isinstance, "True": True, "False": False, "None": None,
}}

_allowed_modules = {allowed_modules!r}

_real_import = builtins.__import__
def _restricted_import(name, *args, **kwargs):
    if name not in _allowed_modules:
        raise ImportError(f"Import of '{{name}}' is not allowed in the sandbox")
    return _real_import(name, *args, **kwargs)

builtins.__import__ = _restricted_import
_allowed_builtins["__import__"] = _restricted_import

exec_globals = {{"__builtins__": _allowed_builtins}}
exec_globals["data"] = {data!r}

try:
    exec({code!r}, exec_globals)
except Exception as e:
    print(f"SANDBOX_ERROR: {{type(e).__name__}}: {{e}}")
'''

def run_sandboxed(code: str, data: list) -> str:
    """
    Executes `code` in a fully separate Python subprocess with:
    - no network access attempted (not blocked at OS level, but no libraries available to make requests)
    - a restricted set of importable modules (math, statistics, re, json, collections only)
    - a restricted builtins set (no open, no eval/exec, no __import__ override bypass)
    - a hard timeout, after which the process is killed
    `data` is the only external data available to the code, injected as a plain list of dicts.
    Returns captured stdout, or an error message.
    """
    script = SANDBOX_TEMPLATE.format(allowed_modules=ALLOWED_MODULES, data=data, code=code)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and not output:
            return f"Sandbox execution failed: {result.stderr.strip()[:300]}"
        return output if output else "(no output produced)"
    except subprocess.TimeoutExpired:
        return f"Sandbox execution timed out after {TIMEOUT_SECONDS} seconds"
    finally:
        os.unlink(script_path)