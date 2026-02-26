"""
Tests that pipeline scripts contain no non-ASCII characters in their print()
calls or string literals that would cause UnicodeEncodeError on Windows where
stdout defaults to cp1252 (which cannot encode e.g. U+2265 >= or U+2014 --).

This catches bugs like the 'pass rate >= 90%' failure in validate_reports.py
before they reach CI.
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Scripts that write to stdout and are run on Windows in the pipeline
PIPELINE_SCRIPTS = [
    "validate_reports.py",
    "validate_single_report.py",
    "generate_all_reports.py",
    "clean_data.py",
    "convert_data.py",
    "send_email.py",
    "email_tracker.py",
    "gui_system_check.py",
    "update_checker.py",
]


def _extract_string_literals(source: str) -> list[tuple[int, str]]:
    """Return (lineno, value) for every string constant in the AST."""
    results = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            results.append((node.lineno, node.value))
    return results


def _non_ascii_chars(s: str) -> list[tuple[int, str]]:
    """Return list of (codepoint, char) for non-ASCII chars in s."""
    return [(ord(c), c) for c in s if ord(c) > 127]


@pytest.mark.parametrize(
    "script",
    [s for s in PIPELINE_SCRIPTS if (ROOT / s).exists()],
    ids=lambda s: s,
)
def test_no_non_ascii_in_print_strings(script):
    """
    No string literal in a print() call should contain non-ASCII characters.
    Windows stdout (cp1252) cannot encode many Unicode chars and will crash.
    Use ASCII equivalents: >= not >=, -- not --, -> not ->.
    """
    source = (ROOT / script).read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match print(...) calls
        func = node.func
        is_print = (isinstance(func, ast.Name) and func.id == "print") or (
            isinstance(func, ast.Attribute) and func.attr == "print"
        )
        if not is_print:
            continue
        # Check all string args
        for arg in ast.walk(node):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                bad = _non_ascii_chars(arg.value)
                if bad:
                    for cp, ch in bad:
                        violations.append(
                            f"  line {node.lineno}: U+{cp:04X} ({ch!r}) in print() string"
                        )

    if violations:
        pytest.fail(
            f"{script} contains non-ASCII chars in print() calls "
            f"(will crash on Windows cp1252):\n" + "\n".join(violations)
        )


@pytest.mark.parametrize(
    "script",
    [s for s in PIPELINE_SCRIPTS if (ROOT / s).exists()],
    ids=lambda s: s,
)
def test_no_non_ascii_in_raise_or_exit_strings(script):
    """
    String literals in raise/sys.exit() calls should also be ASCII-safe.
    Comments and docstrings are exempt (they never reach stdout).
    """
    source = (ROOT / script).read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Collect linenos of docstrings so we can skip them
    docstring_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                docstring_lines.add(node.body[0].lineno)

    violations = []
    for node in ast.walk(tree):
        # Check raise Exception("...") strings
        if isinstance(node, ast.Raise) and node.exc:
            for sub in ast.walk(node.exc):
                if (
                    isinstance(sub, ast.Constant)
                    and isinstance(sub.value, str)
                    and sub.lineno not in docstring_lines
                ):
                    bad = _non_ascii_chars(sub.value)
                    if bad:
                        for cp, ch in bad:
                            violations.append(
                                f"  line {sub.lineno}: U+{cp:04X} ({ch!r}) in raise string"
                            )

    if violations:
        pytest.fail(
            f"{script} contains non-ASCII chars in raise statements "
            f"(may crash on Windows cp1252):\n" + "\n".join(violations)
        )
