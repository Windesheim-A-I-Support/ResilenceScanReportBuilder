"""
Tests that all GitHub Actions workflow files are syntactically valid YAML and
have the expected top-level structure.  Catching a bad workflow file locally
(via pytest) is much faster than waiting for a CI run to fail with "0 jobs".
"""

import pathlib
import re

import pytest
import yaml

WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"


def workflow_files():
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


@pytest.mark.parametrize("wf_path", workflow_files(), ids=lambda p: p.name)
def test_workflow_yaml_valid(wf_path):
    """Every workflow file must parse as valid YAML without errors."""
    text = wf_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        pytest.fail(f"{wf_path.name}: YAML parse error — {exc}")
    assert data is not None, f"{wf_path.name}: parsed to None (empty file?)"


@pytest.mark.parametrize("wf_path", workflow_files(), ids=lambda p: p.name)
def test_workflow_has_name(wf_path):
    """Every workflow file should have a top-level 'name' key."""
    data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    # 'on' parses as True in YAML 1.1; check for name separately
    assert "name" in data, f"{wf_path.name}: missing 'name' key"


@pytest.mark.parametrize("wf_path", workflow_files(), ids=lambda p: p.name)
def test_workflow_has_jobs(wf_path):
    """Every workflow file must have at least one job defined."""
    data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    assert "jobs" in data, f"{wf_path.name}: missing 'jobs' key"
    assert data["jobs"], f"{wf_path.name}: 'jobs' is empty"


@pytest.mark.parametrize("wf_path", workflow_files(), ids=lambda p: p.name)
def test_workflow_run_blocks_indented(wf_path):
    """
    Detect the 'heredoc-at-column-0' bug: in a YAML block scalar (run: |),
    any line starting at column 0 ends the scalar prematurely, causing a parse
    error on GitHub Actions even if local yaml.safe_load() happens to succeed
    (different YAML parsers have different strictness).

    Heuristic: after a 'run: |' line, no subsequent non-empty line should
    start at column 0 until a new top-level YAML key is detected.
    """
    text = wf_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_run_block = False
    run_indent = None
    violations = []

    for lineno, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Detect 'run: |' (or 'run: |-' etc.)
        if re.match(r"\s+run:\s*\|", line):
            in_run_block = True
            run_indent = indent
            continue

        if in_run_block:
            if not stripped:
                continue  # blank lines are fine inside block scalars
            # If we see content at column 0, that's a violation
            if indent == 0 and stripped:
                violations.append((lineno, line))
                in_run_block = False
                run_indent = None
            # If indentation drops to run_indent or less (and it's a key), end block
            elif indent <= run_indent and re.match(r"\s*\w[\w\-]*\s*:", line):
                in_run_block = False
                run_indent = None

    if violations:
        detail = "; ".join(f"line {ln}: {ln_text!r}" for ln, ln_text in violations[:5])
        pytest.fail(
            f"{wf_path.name}: content at column 0 inside a run: | block "
            f"(breaks YAML block scalar) — {detail}"
        )
